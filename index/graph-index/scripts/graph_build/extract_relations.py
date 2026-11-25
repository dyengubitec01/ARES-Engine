# -*- coding: utf-8 -*-
"""그래프 관계추출 레이어 (per-chunk LLM) — 공출현 엣지에 '진짜 관계' 라벨 부여.

설계 (build_graph 와의 차이):
  build_graph = GLiNER2 엔티티 + **라벨 없는 공출현** 엣지.
  이 스크립트 = 그 위에 청크별 LLM 1콜로, **GLiNER2가 이미 뽑은 엔티티들 사이**
                실제 관계만 추출(엔티티 재추출 X). 같은 청크에 함께 나왔다고 다
                관계가 아니라, 본문에 명시된 것만 → 공출현 junk(hub glue) 가지치기.

스모크 모드(기본): dev active 빌드에서 다(多)엔티티 청크 샘플 → 콘솔 출력만(DB 안 씀).
  목적 = 프롬프트 품질·hub 가지치기·환각여부를 눈으로 검증한 뒤 prod 16만 풀런 결정.

핵심 지표:
  - prune ratio = 관계수 / 공출현쌍수.  낮을수록 LLM이 junk 공출현을 잘 쳐냄(목표).
  - hub 가지치기 = AI/CCTV/스마트시티 같은 고빈도어가 근거 없이 관계로 안 묶이는지.
  - 환각 = 목록 밖 엔티티를 지어내는지(검증 후 drop 카운트).

실행(스모크):
  .venv/Scripts/python.exe scripts/graph_build/extract_relations.py --db dev \
     --gemma-url http://localhost:8000 --gemma-key sk-... \
     --limit 15
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import requests
from sqlalchemy import create_engine, text

from config import settings

_WS = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """build_graph.normalize_name 와 동일 키(공백완전제거+casefold)."""
    return _WS.sub("", (name or "").strip()).casefold()


# full_relational.py 관계 정규화 재사용(영문/구두점 표기 → 한글 대표어)
RELATION_MAP = {
    "HAS_DATA": "보유", "CONTAINS": "포함", "HAS_COMPONENT": "구성",
    "HAS_PART": "구성", "COMPONENT_OF": "구성", "IS_PART_OF": "구성",
    "PART_OF": "구성", "USES": "사용", "USED_FOR": "용도", "RELATED": "관련",
    "RELATED_TO": "관련", "COLLABORATES_WITH": "협력", "DEVELOPED_BY": "개발",
    "DEPLOYED_ON": "배포", "IMPLEMENTED_BY": "구축", "PROJECT_OWNER": "소유",
}


def normalize_relation_type(rtype: str) -> str:
    if not rtype:
        return "관련"
    return RELATION_MAP.get(rtype.upper().strip(), rtype.strip())


SYSTEM_PROMPT = """당신은 한국어 문서에서 엔티티 간 관계를 추출하는 전문가입니다.
주어진 [엔티티 목록] 안의 엔티티들 사이에, [본문]에 명시적으로 드러난 관계만 추출하세요.

[엄격 규칙]
1. source/target 은 반드시 [엔티티 목록]에 있는 이름과 정확히 일치. 목록에 없는 엔티티 금지.
2. 본문에 근거가 없으면 관계를 만들지 마세요. 같은 문단에 함께 나왔다는 것만으로는 관계가 아닙니다.
   명시적 서술(누가 무엇을 한다/구성한다/사용한다 등)이 있을 때만.
3. AI, IoT, CCTV, ICT, 스마트시티처럼 문서 전반에 흔히 나오는 일반/도메인 핵심어는,
   구체적 관계 서술이 없으면 관계로 묶지 마세요.
4. evidence 에는 근거가 된 본문 구절을 20자 이내로 짧게 인용(길면 핵심만).
5. 출력은 오직 유효한 JSON 객체만. 마크다운 코드블록·부가 설명 금지.

[관계 type] 구성, 포함, 사용, 개발, 운영, 협력, 제공, 적용, 담당, 관련 중 가장 적합한 것.
마땅한 게 없으면 본문 표현을 짧은 동사구로.

[출력 형식]
{"relations": [{"source": "엔티티명", "target": "엔티티명", "type": "관계명", "evidence": "본문 근거"}]}
관계가 없으면: {"relations": []}"""


def build_user_message(chunk_text: str, entities: list[tuple[str, str]], max_text: int) -> str:
    txt = (chunk_text or "")[:max_text]
    lines = "\n".join(f"{i}. {name} ({etype})" for i, (name, etype) in enumerate(entities, 1))
    return f"[본문]\n{txt}\n\n[엔티티 목록]\n{lines}"


def gemma(sess, url, key, model, system, user, max_tokens=2500, timeout=180, max_retries=4):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = {
        "model": model, "temperature": 0, "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    endpoint = url.rstrip("/") + "/v1/chat/completions"
    last = None
    for attempt in range(1, max_retries + 1):
        try:
            r = sess.post(endpoint, json=body, headers=headers, timeout=(10, timeout))
            r.raise_for_status()
            j = r.json()
            return j["choices"][0]["message"]["content"], j.get("usage", {})
        except requests.exceptions.RequestException as e:
            last = e
            if attempt == max_retries:
                break
            time.sleep(min(2 ** attempt, 20))  # 2,4,8,16 — 404/timeout 일시장애 대비
    raise last


def parse_json(content: str) -> dict:
    s = (content or "").strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    if s.startswith("```"):
        lines = s.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    # 본문에 섞인 첫 { ... 마지막 } 만 추출 시도
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"_parse_error": True, "_raw": content}


def make_engine(db):
    schema = "rag_dev" if db == "dev" else settings.postgres_schema
    dbname = "ragdb_dev" if db == "dev" else settings.postgres_db
    url = (f"postgresql://{settings.postgres_user}:{quote_plus(settings.postgres_password)}"
           f"@{settings.postgres_host}:{settings.postgres_port}/{dbname}")
    return create_engine(url, connect_args={"options": f"-csearch_path={schema},public"}), dbname, schema


def sample_chunks(eng, build_id, min_ent, max_ent, limit, mode):
    """active 빌드에서 엔티티 수 [min_ent, max_ent]인 청크 샘플.
    mode=hard  → 엔티티 많은 순(hub 가지치기 스트레스, 품질 검증용)
    mode=spread→ md5 의사난수 정렬(대표 분포, 실제 throughput 추정용)."""
    order = "ne DESC" if mode == "hard" else "md5(chunk_id::text)"
    with eng.connect() as c:
        rows = c.execute(text(
            "SELECT chunk_id, count(DISTINCT entity_id) ne FROM rag_graph_entity_chunks "
            "WHERE build_id=:b GROUP BY chunk_id "
            "HAVING count(DISTINCT entity_id) BETWEEN :lo AND :hi "
            f"ORDER BY {order} LIMIT :n"),
            {"b": build_id, "lo": min_ent, "hi": max_ent, "n": limit}).fetchall()
    return [(str(cid), ne) for cid, ne in rows]


def total_relation_chunks(eng, build_id, min_ent):
    """관계추출 콜이 필요한 청크 수(엔티티>=min_ent) — 16만 환산 분모."""
    with eng.connect() as c:
        return c.execute(text(
            "SELECT count(*) FROM (SELECT chunk_id FROM rag_graph_entity_chunks WHERE build_id=:b "
            "GROUP BY chunk_id HAVING count(DISTINCT entity_id) >= :lo) q"),
            {"b": build_id, "lo": min_ent}).scalar()


def get_chunk(eng, build_id, chunk_id):
    with eng.connect() as c:
        txt = c.execute(text("SELECT text FROM rag_chunks WHERE id=:i"), {"i": chunk_id}).scalar()
        ents = c.execute(text(
            "SELECT e.name, e.entity_type FROM rag_graph_entities e "
            "JOIN rag_graph_entity_chunks ec ON ec.entity_id=e.id "
            "WHERE ec.build_id=:b AND ec.chunk_id=:c ORDER BY e.chunk_count DESC"),
            {"b": build_id, "c": chunk_id}).fetchall()
    return txt or "", [(n, t) for n, t in ents]


def process_chunk(sess, args, bid, eng, cid):
    """한 청크 처리 → 결과 dict(콘솔/집계용). DB 미반영."""
    txt, ents = get_chunk(eng, bid, cid)
    if len(ents) < 2:
        return None
    ents = ents[:args.max_ent_per_call]
    norm_to_name = {normalize_name(n): n for n, _ in ents}
    pairs = math.comb(len(ents), 2)
    user = build_user_message(txt, ents, args.max_text)
    t0 = time.time()
    try:
        content, _ = gemma(sess, args.gemma_url, args.gemma_key, args.gemma_model, SYSTEM_PROMPT, user)
    except Exception as e:
        return {"cid": cid, "ents": ents, "pairs": pairs, "error": str(e), "dt": time.time() - t0}
    dt = time.time() - t0
    parsed = parse_json(content)
    if parsed.get("_parse_error"):
        return {"cid": cid, "ents": ents, "pairs": pairs, "parse_error": True,
                "raw": content[:200], "dt": dt}
    kept, dropped = [], 0
    for r in parsed.get("relations") or []:
        if not isinstance(r, dict):
            continue
        sn, tn = normalize_name(r.get("source", "")), normalize_name(r.get("target", ""))
        if sn in norm_to_name and tn in norm_to_name and sn != tn:
            kept.append((norm_to_name[sn], norm_to_name[tn],
                         normalize_relation_type(r.get("type", "관련")), (r.get("evidence") or "").strip()))
        else:
            dropped += 1
    return {"cid": cid, "ents": ents, "pairs": pairs, "kept": kept, "dropped": dropped,
            "norms": set(norm_to_name), "involved": {normalize_name(k[0]) for k in kept} | {normalize_name(k[1]) for k in kept},
            "dt": dt}


# ════════════════════════════════════════════════════════════════════
#  프로덕션 저장 모드 (--store): 캐시(재개·델타) + 엣지 라벨 기록
# ════════════════════════════════════════════════════════════════════
CHUNK_REL_KIND = "chunk_relations"


def chunk_cache_key(txt: str) -> str:
    """청크 텍스트 sha256 → cross-build 캐시 키. 텍스트 동일하면 재사용(재개/델타)."""
    return "chunkrel:" + hashlib.sha256((txt or "").encode("utf-8")).hexdigest()[:48]


def list_target_chunks(eng, build_id, min_ent):
    """관계콜 대상 chunk_id (엔티티>=min_ent)."""
    with eng.connect() as c:
        rows = c.execute(text(
            "SELECT chunk_id FROM rag_graph_entity_chunks WHERE build_id=:b "
            "GROUP BY chunk_id HAVING count(DISTINCT entity_id) >= :lo"),
            {"b": build_id, "lo": min_ent}).fetchall()
    return [str(r[0]) for r in rows]


def load_batch(eng, build_id, ids):
    """배치 chunk_id → {cid: (text, [(name,type)])}."""
    out = {}
    with eng.connect() as c:
        for cid, txt in c.execute(text("SELECT id, text FROM rag_chunks WHERE id = ANY(CAST(:ids AS uuid[]))"),
                                  {"ids": ids}).fetchall():
            out[str(cid)] = [txt or "", []]
        rows = c.execute(text(
            "SELECT ec.chunk_id, e.name, e.entity_type FROM rag_graph_entity_chunks ec "
            "JOIN rag_graph_entities e ON ec.entity_id = e.id "
            "WHERE ec.build_id=:b AND ec.chunk_id = ANY(CAST(:ids AS uuid[])) ORDER BY e.chunk_count DESC"),
            {"b": build_id, "ids": ids}).fetchall()
    for cid, name, etype in rows:
        scid = str(cid)
        if scid in out:
            out[scid][1].append((name, etype))
    return out


def extract_relations_for_chunk(sess, args, txt, ents):
    """LLM 1콜 → 검증된 관계 [[src_norm, tgt_norm, type, evidence], ...]. (DB 미접근=스레드 안전).
    엔티티 cap: 리스트/표 청크(엔티티 수십~100+, 텍스트 짧음)는 출력이 max_tokens 초과→절단→
    파싱실패+재시도tax. 상위 N개(chunk_count順)로 캡해 출력 bounded(리스트 항목간 관계는 어차피 저가치)."""
    ents = ents[:args.max_ent_per_call]
    norm_to_name = {normalize_name(n): n for n, _ in ents}
    user = build_user_message(txt, ents, args.max_text)
    content, _ = gemma(sess, args.gemma_url, args.gemma_key, args.gemma_model, SYSTEM_PROMPT, user)
    parsed = parse_json(content)
    if parsed.get("_parse_error"):
        return None
    rels = []
    for r in parsed.get("relations") or []:
        if not isinstance(r, dict):
            continue
        sn, tn = normalize_name(r.get("source", "")), normalize_name(r.get("target", ""))
        if sn in norm_to_name and tn in norm_to_name and sn != tn:
            rels.append([sn, tn, normalize_relation_type(r.get("type", "관련")), (r.get("evidence") or "")[:80]])
    return rels


def run_store(eng, bid, args):
    """active 빌드에 per-chunk 관계추출 → 캐시 적재 + 엣지 relation_label 기록.
    Phase A(비쌈·재개가능): 캐시에 없는 청크만 LLM, 배치마다 커밋(체크포인트).
    Phase B(쌈·멱등): 캐시→엣지 매핑, relation_label 일괄 UPDATE."""
    sess = requests.Session()
    target = list_target_chunks(eng, bid, args.min_ent)
    print(f"[store] 대상 청크 {len(target)} (엔티티>={args.min_ent})")

    # 이미 캐시된 해시 (재개/델타)
    with eng.connect() as c:
        cached = {r[0] for r in c.execute(text(
            "SELECT cache_key FROM rag_graph_summary_cache WHERE summary_kind=:k"),
            {"k": CHUNK_REL_KIND}).fetchall()}
    print(f"[store] 기존 캐시 {len(cached)}개 — 재개/델타로 스킵")

    BATCH = 256
    done = reused = called = parse_fail = 0
    used_keys = set()   # 이번 런이 실제로 참조/기록한 캐시 키 → 끝에서 last_used_at 스탬프
    t0 = time.time()
    for i in range(0, len(target), BATCH):
        ids = target[i:i + BATCH]
        loaded = load_batch(eng, bid, ids)
        todo = []  # (cid, hkey, text, ents)
        for cid in ids:
            txt, ents = loaded.get(cid, ["", []])
            if len(ents) < 2:
                continue
            hkey = chunk_cache_key(txt)
            used_keys.add(hkey)
            if hkey in cached:
                reused += 1
                continue
            todo.append((cid, hkey, txt, ents))

        new_rows = {}  # hkey -> json (dedup: 같은 텍스트 중복 청크 1회만)
        if todo:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = {ex.submit(extract_relations_for_chunk, sess, args, t, e): h
                        for (_c, h, t, e) in todo}
                for f in as_completed(futs):
                    h = futs[f]
                    try:
                        rels = f.result()
                    except Exception:
                        rels = None
                    if rels is None:
                        parse_fail += 1
                        continue
                    new_rows[h] = json.dumps(rels, ensure_ascii=False)
                    called += 1
        # 배치 커밋 = 체크포인트
        if new_rows:
            with eng.begin() as c:
                for hkey, js in new_rows.items():
                    c.execute(text(
                        "INSERT INTO rag_graph_summary_cache (cache_key, summary_kind, summary_text, model_name) "
                        "VALUES (:k, :kind, :s, :m) ON CONFLICT (cache_key) DO NOTHING"),
                        {"k": hkey, "kind": CHUNK_REL_KIND, "s": js, "m": args.gemma_model})
            cached |= set(new_rows)
        done += len(ids)
        el = time.time() - t0
        rate = called / el if el else 0
        print(f"  [{done}/{len(target)}] 재사용 {reused} / LLM {called} / 파싱실패 {parse_fail} "
              f"| {rate:.2f}콜/s, 경과 {el/60:.1f}m", flush=True)

    # ── Phase B: 캐시 → 엣지 매핑. 기존 엣지=라벨 UPDATE / orphan(weight<2 가지치기로
    #    엣지없음)=LLM 확정관계라 새 엣지로 승격 INSERT(weight=1, llm_promoted). 멱등(재실행시
    #    승격분은 edgemap에 있어 UPDATE로 빠짐). ──
    print("[store] Phase B: 엣지 라벨 UPDATE + orphan 관계 엣지 승격...")
    with eng.connect() as c:
        edgemap = {}  # "n1\x00n2"(sorted) -> edge_id (기존 엣지)
        for eid, sn, tn in c.execute(text(
                "SELECT e.id, s.normalized_name, t.normalized_name FROM rag_graph_edges e "
                "JOIN rag_graph_entities s ON e.source_entity_id=s.id "
                "JOIN rag_graph_entities t ON e.target_entity_id=t.id WHERE e.build_id=:b"),
                {"b": bid}).fetchall():
            edgemap["\x00".join(sorted([sn, tn]))] = eid
        # norm -> entity_id (동명이타입은 chunk_count 최다 = 대표)
        norm2id = {}
        for nn, eid, cc in c.execute(text(
                "SELECT normalized_name, id, chunk_count FROM rag_graph_entities WHERE build_id=:b "
                "ORDER BY chunk_count"), {"b": bid}).fetchall():
            norm2id[nn] = eid  # ORDER BY asc → 마지막(최다 chunk_count) 승리
        # resolution alias 맵: 캐시 관계는 옛 변형 norm(스마트시티)으로 저장됐는데, resolution이
        # 그래프에선 canonical(스마트도시)로 병합해 변형 노드가 없음 → 변형 norm을 canonical로
        # 치환해야 매핑됨. 안 하면 unmapped로 관계 손실(build_graph가 쓰는 그 맵을 동일 적용).
        amap = {}
        arow = c.execute(text("SELECT summary_text FROM rag_graph_summary_cache WHERE cache_key='alias_map:v1'")).scalar()
        if arow:
            try: amap = json.loads(arow).get("map") or {}
            except (ValueError, TypeError): amap = {}
    if amap:
        print(f"    alias 맵 적용(캐시 관계 norm→canonical): 변형 {len(amap)}개")

    updates = {}    # edge_id -> set(types)  (기존 엣지)
    promote = {}    # "n1\x00n2"(sorted) -> {"src": sn, "tgt": tn, "types": set}  (orphan 승격)
    unmapped = 0
    for i in range(0, len(target), BATCH):
        ids = target[i:i + BATCH]
        loaded = load_batch(eng, bid, ids)
        with eng.connect() as c:
            for cid in ids:
                txt = loaded.get(cid, ["", []])[0]
                row = c.execute(text("SELECT summary_text FROM rag_graph_summary_cache WHERE cache_key=:k"),
                                {"k": chunk_cache_key(txt)}).scalar()
                if not row:
                    continue
                for sn, tn, rtype, _ev in json.loads(row):
                    sn = amap.get(sn, sn); tn = amap.get(tn, tn)  # resolution 변형→canonical
                    if sn == tn:           # 병합으로 같은 엔티티 된 쌍 = self-loop, 스킵
                        continue
                    key = "\x00".join(sorted([sn, tn]))
                    eid = edgemap.get(key)
                    if eid is not None:
                        updates.setdefault(eid, set()).add(rtype)
                    elif sn in norm2id and tn in norm2id:
                        p = promote.setdefault(key, {"src": sn, "tgt": tn, "types": set()})
                        p["types"].add(rtype)
                    else:
                        unmapped += 1  # 이론상 0 (추출이 빌드 엔티티로 검증됨)

    # 기존 엣지 라벨 UPDATE
    upd_rows = [{"e": eid, "l": ", ".join(sorted(types))} for eid, types in updates.items()]
    with eng.begin() as c:
        for j in range(0, len(upd_rows), 1000):
            for r in upd_rows[j:j + 1000]:
                c.execute(text("UPDATE rag_graph_edges SET relation_label=:l WHERE id=:e"),
                          {"l": r["l"], "e": r["e"]})

    # orphan 승격 INSERT (weight=1, metadata.llm_promoted)
    ins_rows = [{
        "b": bid, "s": norm2id[p["src"]], "t": norm2id[p["tgt"]],
        "l": ", ".join(sorted(p["types"])),
        "m": json.dumps({"llm_promoted": True, "basis": "single_cooccur_llm_confirmed"}, ensure_ascii=False),
    } for p in promote.values()]
    with eng.begin() as c:
        for j in range(0, len(ins_rows), 1000):
            c.execute(text(
                "INSERT INTO rag_graph_edges (build_id, source_entity_id, target_entity_id, weight, relation_label, metadata) "
                "VALUES (:b, :s, :t, 1, :l, CAST(:m AS jsonb))"), ins_rows[j:j + 1000])

        # builds.edge_count 정합화 — build_graph 가 찍은 값에는 위 승격분이 빠져 있어
        # 그 컬럼으로 모니터링하면 그래프가 축소 보고된다(build41: 894,904 기록 / 실제 996,432).
        # 승격과 같은 트랜잭션에서 실제 row 수로 재계산 → 멱등(재실행·승격 0건이어도 안전).
        c.execute(text(
            "UPDATE rag_graph_builds SET edge_count = "
            "(SELECT count(*) FROM rag_graph_edges WHERE build_id = :b) WHERE id = :b"),
            {"b": bid})

    # 캐시 last_used_at 스탬프 — 미사용 행 회수(LRU) 판단 근거. 히트마다 UPDATE 하면
    # 12만+ UPDATE/빌드가 되므로 런 끝에 1만 단위 배치로 한 번만 찍는다.
    if used_keys:
        keys = list(used_keys)
        with eng.begin() as c:
            for j in range(0, len(keys), 10000):
                c.execute(text("UPDATE rag_graph_summary_cache SET last_used_at=now() "
                               "WHERE cache_key = ANY(:ks)"), {"ks": keys[j:j + 10000]})

    print(f"[store 완료] 기존엣지 라벨 {len(upd_rows)} / orphan 승격 INSERT {len(ins_rows)} "
          f"(unmapped {unmapped}) / 캐시 총 {len(cached)} / 이번 LLM {called} "
          f"/ last_used_at 스탬프 {len(used_keys)}")


def main():
    ap = argparse.ArgumentParser(description="per-chunk LLM 관계추출 스모크")
    ap.add_argument("--db", default="dev")
    ap.add_argument("--gemma-url", default=os.getenv("GEMMA_API_URL"))
    ap.add_argument("--gemma-key", default=os.getenv("GEMMA_API_KEY", ""))
    ap.add_argument("--gemma-model", default="gemma-4-31b")
    ap.add_argument("--limit", type=int, default=15, help="샘플 청크 수")
    ap.add_argument("--min-ent", type=int, default=2, help="청크 최소 엔티티 수(2=쌍도 포함)")
    ap.add_argument("--max-ent", type=int, default=25, help="청크 최대 엔티티 수(프롬프트 폭주 방지)")
    ap.add_argument("--max-ent-per-call", type=int, default=40,
                    help="콜당 엔티티 상한(초과시 상위 chunk_count순 절단). 리스트/표 청크 출력 절단 방지.")
    ap.add_argument("--max-text", type=int, default=3000, help="본문 최대 글자")
    ap.add_argument("--mode", choices=["hard", "spread"], default="hard",
                    help="hard=엔티티많은순(품질), spread=대표분포(throughput 추정)")
    ap.add_argument("--workers", type=int, default=1, help="동시 호출 수")
    ap.add_argument("--quiet", action="store_true", help="청크별 관계 상세 생략(throughput 측정용)")
    ap.add_argument("--store", action="store_true",
                    help="프로덕션 모드: active 빌드 전체 관계추출 → 캐시 적재 + 엣지 relation_label 기록(재개·델타)")
    args = ap.parse_args()
    if not args.gemma_url:
        raise SystemExit("--gemma-url (또는 GEMMA_API_URL) 필요")

    eng, dbname, schema = make_engine(args.db)
    with eng.connect() as c:
        bid = c.execute(text("SELECT id FROM rag_graph_builds WHERE status='active' ORDER BY id DESC LIMIT 1")).scalar()
    if bid is None:
        raise SystemExit("active 빌드 없음")

    if args.store:
        print(f"[{dbname}.{schema}] active build {bid} — 관계추출 STORE "
              f"(min_ent={args.min_ent}, workers={args.workers})")
        run_store(eng, bid, args)
        return

    denom = total_relation_chunks(eng, bid, args.min_ent)
    print(f"[{dbname}.{schema}] active build {bid} — 관계추출 스모크 "
          f"{args.limit}청크 (엔티티 {args.min_ent}~{args.max_ent}, mode={args.mode}, workers={args.workers})")
    print(f"  관계콜 대상 청크(엔티티>={args.min_ent}) 총 {denom}개 = 16만 환산 분모\n")

    chunks = sample_chunks(eng, bid, args.min_ent, args.max_ent, args.limit, args.mode)
    if not chunks:
        raise SystemExit("샘플 청크 없음")

    sess = requests.Session()
    results = []
    wall0 = time.time()
    if args.workers <= 1:
        for cid, _ in chunks:
            results.append(process_chunk(sess, args, bid, eng, cid))
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(process_chunk, sess, args, bid, eng, cid): cid for cid, _ in chunks}
            for f in as_completed(futs):
                results.append(f.result())
    wall = time.time() - wall0
    results = [r for r in results if r]

    tot_ent = tot_pairs = tot_rel = tot_dropped = 0
    parse_errors = call_errors = 0
    sum_dt = 0.0
    rel_involved = set(); all_norm = set()
    for idx, r in enumerate(results, 1):
        sum_dt += r.get("dt", 0)
        ents, pairs = r["ents"], r["pairs"]
        if r.get("error"):
            call_errors += 1
            if not args.quiet:
                print(f"[{idx}] chunk={r['cid'][:8]} 호출실패: {r['error']}")
            continue
        if r.get("parse_error"):
            parse_errors += 1
            if not args.quiet:
                print(f"[{idx}] chunk={r['cid'][:8]}  엔티티 {len(ents)}  쌍 {pairs}  ⚠️ 파싱실패 ({r['dt']:.1f}s)")
                print(f"     raw: {r['raw']}")
            continue
        kept = r["kept"]
        tot_ent += len(ents); tot_pairs += pairs; tot_rel += len(kept); tot_dropped += r["dropped"]
        all_norm |= r["norms"]; rel_involved |= r["involved"]
        if not args.quiet:
            ratio = len(kept) / pairs if pairs else 0
            print(f"[{idx}] chunk={r['cid'][:8]}  엔티티 {len(ents)}  공출현쌍 {pairs}  "
                  f"관계 {len(kept)}  (prune {ratio:.0%}{', 환각drop '+str(r['dropped']) if r['dropped'] else ''})  {r['dt']:.1f}s")
            ent_preview = ", ".join(n for n, _ in ents[:8]) + ("..." if len(ents) > 8 else "")
            print(f"     엔티티: {ent_preview}")
            for s, t, ty, ev in kept[:12]:
                print(f"       • {s} —[{ty}]→ {t}" + (f"  「{ev[:40]}」" if ev else ""))
            if not kept:
                print("       (관계 없음)")
            print()

    n = len(results)
    ok = n - parse_errors - call_errors
    print("=" * 70)
    print(f"[집계] 청크 {n} / 성공 {ok} / 파싱실패 {parse_errors} / 호출실패 {call_errors}")
    if tot_ent:
        print(f"  평균 엔티티/청크 = {tot_ent/ok:.1f}, 평균 공출현쌍/청크 = {tot_pairs/ok:.1f}, 평균 관계/청크 = {tot_rel/ok:.1f}")
        print(f"  전체 prune ratio = 관계 {tot_rel} / 공출현쌍 {tot_pairs} = {tot_rel/max(tot_pairs,1):.1%} (낮을수록 junk 공출현 잘 쳐냄)")
        print(f"  환각(목록 밖) drop = {tot_dropped}")
        print(f"  관계에 안 묶인 엔티티 = {len(all_norm - rel_involved)}/{len(all_norm)}")
    # ── throughput ──
    print(f"\n[throughput] wall {wall:.1f}s, workers {args.workers}, 처리 {n}청크")
    print(f"  평균 콜 지연 = {sum_dt/max(n,1):.1f}s/청크 (개별)")
    if wall > 0:
        cps = n / wall
        print(f"  실효 처리량 = {cps:.2f}청크/s (동시성 반영)")
        print(f"  → 16만 환산({denom}청크): {denom/cps/3600:.1f}h @ workers={args.workers}")
    print("\n[스모크 종료] DB 미반영. 결과·throughput 보고 prod 풀런 + 저장 로직 결정.")


if __name__ == "__main__":
    main()
