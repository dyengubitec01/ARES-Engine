# -*- coding: utf-8 -*-
"""엔티티 description 생성 스테이지 (per-entity LLM) — 엔티티가 무엇인지 1~2문장 설명.

대상: active 빌드에서 chunk_count >= min-chunk-count 엔티티(기본 2). 1청크 엔티티는
설명 재료가 한 문장뿐이라 제외. 결과는 rag_graph_entities.description 에 저장.

캐싱(extract_relations 패턴 재사용): rag_graph_summary_cache(summary_kind='entity_desc').
키 = hash(normalized_name + 대표청크 발췌). 입력 동일하면 재사용 → 첫 빌드만 비싸고 이후 델타.
"설명 불가"(근거 불충분) 응답은 캐시는 하되 description 컬럼엔 NULL(노이즈 방지).
단 그 캐시가 다음 빌드에서도 재사용돼 **영구 차단**되므로(build41 실측: 적격 79,654 중
15,439개가 이 사유로 NULL) 재시도 수단으로 --retry-negatives 를 둔다 — 지정 시 부정 캐시를
미스로 취급해 LLM 을 다시 호출한다. 미지정이 기본(야간 상시비용 0).
주의: gemma temperature=0 이라 같은 입력엔 같은 답이 나온다. 따라서 --retry-negatives 가
실효를 갖는 건 **프롬프트나 모델을 바꿨을 때**뿐이다(둘 다 cache_key 에 안 들어가므로
그냥 두면 개선이 실패 엔티티에 영원히 닿지 않는다). 반대로 **발췌 선정을 바꾸면**
cache_key=hash(정규화명+발췌) 가 알아서 달라져 캐시 미스로 재호출되므로 이 플래그가
필요 없다 — 발췌 선정은 load_excerpts 주석 참고.

실행:
  .venv/Scripts/python.exe scripts/graph_build/describe_entities.py --db prod \
     --gemma-url https://... --gemma-key sk-... --workers 32 --min-chunk-count 2
  # 부정 캐시 따라잡기(1회성):
  .venv/Scripts/python.exe scripts/graph_build/describe_entities.py --db prod --retry-negatives
"""
from __future__ import annotations
import argparse
import hashlib
import os
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

ENTITY_DESC_KIND = "entity_desc"

SYSTEM_PROMPT = """당신은 문서에서 특정 엔티티가 무엇인지 설명하는 전문가입니다.
주어진 [엔티티]에 대해 [발췌]에 근거해서만 한국어 1~2문장으로 설명하세요.

[규칙]
1. 발췌에 드러난 사실만 사용. 외부지식·추측 금지.
2. 근거가 불충분하면 정확히 '설명 불가'라고만 답하세요.
3. 군더더기 없이 핵심만. 마크다운·목록 금지, 평문 1~2문장."""


def make_engine(db):
    schema = "rag_dev" if db == "dev" else settings.postgres_schema
    dbname = "ragdb_dev" if db == "dev" else settings.postgres_db
    url = (f"postgresql://{settings.postgres_user}:{quote_plus(settings.postgres_password)}"
           f"@{settings.postgres_host}:{settings.postgres_port}/{dbname}")
    return create_engine(url, connect_args={"options": f"-csearch_path={schema},public"}), dbname, schema


def gemma(sess, url, key, model, system, user, max_tokens=200, timeout=120, max_retries=4):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = {"model": model, "temperature": 0, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    endpoint = url.rstrip("/") + "/v1/chat/completions"
    last = None
    for attempt in range(1, max_retries + 1):
        try:
            r = sess.post(endpoint, json=body, headers=headers, timeout=(10, timeout))
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.RequestException as e:
            last = e
            if attempt == max_retries:
                break
            time.sleep(min(2 ** attempt, 20))  # 2,4,8,16 — 일시장애 대비
    raise last


def cache_key(norm: str, excerpts: str) -> str:
    """입력(정규화명 + 발췌) 해시. 동일 입력 → 동일 설명 → 재사용(cross-build)."""
    return "entdesc:" + hashlib.sha256((norm + "\x00" + excerpts).encode("utf-8")).hexdigest()[:48]


def clean_desc(d: str):
    """'설명 불가'·빈약 응답은 None(컬럼 NULL). null바이트 제거(Postgres text 거부 방지)."""
    d = (d or "").replace("\x00", "").strip()
    if not d or len(d) < 4 or d.startswith("설명 불가"):
        return None
    return d


def list_targets(eng, bid, min_cc, limit):
    with eng.connect() as c:
        sql = ("SELECT id, name, normalized_name FROM rag_graph_entities "
               "WHERE build_id=:b AND chunk_count >= :m ORDER BY chunk_count DESC")
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = c.execute(text(sql), {"b": bid, "m": min_cc}).fetchall()
    return [(str(r[0]), r[1], r[2]) for r in rows]


def load_excerpts(eng, bid, eids, k, max_text):
    """배치 엔티티 → {eid: 발췌}. 엔티티별 LATERAL LIMIT(인덱스 사용, 엔티티별 소량 정렬)로
    대형 window 정렬을 피함. 병렬쿼리도 끔 — 큰 window 정렬이 병렬 DSM(/dev/shm 64MB)을
    초과해 DiskFull 크래시 냈던 것 방지.

    발췌 선정 = occurrence_count 내림차순. 옛 방식(ORDER BY ch.id)은 UUID 순이라 사실상
    무작위 k개였고, 수천 청크에 등장하는 허브 엔티티일수록 표/목차 조각만 뽑혀 LLM 이
    '설명 불가'로 답했다(build42 실측: 적격 79,654 중 15,439개 NULL, 그 중 인공지능
    6,730청크·VMS 3,234청크 등 최상위 허브 포함). occurrence_count 는 "그 청크가 이 엔티티를
    실제로 다루는가"의 대리지표 — 표에서는 셀에 1회 스치지만 설명 문단에서는 반복된다.
    표본 60개 실측: 옛 방식 0/60 → 신규 11/60 회복.

    2차 정렬키 ch.id 는 필수. occurrence_count 동률이 대량이므로 tie-break 가 없으면
    발췌 순서가 빌드마다 흔들리고, cache_key=hash(정규화명+발췌) 가 매번 달라져 캐시가
    영구 무효화된다(매 빌드 전량 재호출).
    """
    with eng.connect() as c:
        c.execute(text("SET max_parallel_workers_per_gather = 0"))
        rows = c.execute(text(
            "SELECT e.eid, x.txt FROM unnest(CAST(:ids AS uuid[])) AS e(eid) "
            "CROSS JOIN LATERAL ("
            "  SELECT ch.text AS txt FROM rag_graph_entity_chunks ec "
            "  JOIN rag_chunks ch ON ec.chunk_id = ch.id "
            "  WHERE ec.build_id = :b AND ec.entity_id = e.eid "
            "  ORDER BY ec.occurrence_count DESC, ch.id LIMIT :k"
            ") AS x"),
            {"b": bid, "ids": eids, "k": k}).fetchall()
    grouped = {}
    for eid, txt in rows:
        grouped.setdefault(str(eid), []).append((txt or "")[:max_text])
    return {eid: "\n---\n".join(texts) for eid, texts in grouped.items()}


def main():
    ap = argparse.ArgumentParser(description="엔티티 description 생성(per-entity LLM, 캐시)")
    ap.add_argument("--db", default="dev")
    ap.add_argument("--gemma-url", default=os.getenv("GEMMA_API_URL"))
    ap.add_argument("--gemma-key", default=os.getenv("GEMMA_API_KEY", ""))
    ap.add_argument("--gemma-model", default="gemma-4-31b")
    ap.add_argument("--min-chunk-count", type=int, default=2,
                    help="이 청크수 이상 엔티티만 설명(기본 2). 1=재료 한 문장뿐이라 제외")
    ap.add_argument("--max-chunks", type=int, default=5, help="설명 근거로 쓸 대표 청크 수")
    ap.add_argument("--max-text", type=int, default=500, help="청크당 발췌 글자")
    ap.add_argument("--workers", type=int, default=32, help="동시 LLM 호출 수")
    ap.add_argument("--limit", type=int, default=None, help="대상 엔티티 상한(스모크용)")
    ap.add_argument("--retry-negatives", action="store_true",
                    help="캐시된 '설명 불가'(부정) 응답을 미스로 취급해 LLM 재호출. 미지정시 재사용"
                         "(야간 추가비용 0). 발췌가 그대로면 결과도 대체로 동일함에 유의")
    args = ap.parse_args()
    if not args.gemma_url:
        raise SystemExit("--gemma-url (또는 GEMMA_API_URL) 필요")

    eng, dbname, schema = make_engine(args.db)
    with eng.connect() as c:
        bid = c.execute(text("SELECT id FROM rag_graph_builds WHERE status='active' ORDER BY id DESC LIMIT 1")).scalar()
    if bid is None:
        raise SystemExit("active 빌드 없음")

    targets = list_targets(eng, bid, args.min_chunk_count, args.limit)
    print(f"[{dbname}.{schema}] active build {bid} — 엔티티 description "
          f"대상 {len(targets)} (chunk_count >= {args.min_chunk_count}, workers={args.workers})")

    with eng.connect() as c:
        cached = {r[0]: r[1] for r in c.execute(text(
            "SELECT cache_key, summary_text FROM rag_graph_summary_cache WHERE summary_kind=:k"),
            {"k": ENTITY_DESC_KIND}).fetchall()}
    n_cached = len(cached)
    n_neg_cached = sum(1 for v in cached.values() if clean_desc(v) is None)
    if args.retry_negatives and n_neg_cached:
        # 부정 캐시를 미스로 되돌려 재호출 대상에 포함. 성공분은 아래 INSERT 의
        # ON CONFLICT DO UPDATE 가 옛 부정행을 덮어써 다음 빌드에 되살아나지 않게 한다.
        cached = {k: v for k, v in cached.items() if clean_desc(v) is not None}
    print(f"[캐시] 기존 {n_cached}개 (부정 {n_neg_cached}개) — 재개/델타로 스킵"
          + (f" | --retry-negatives: 부정 {n_neg_cached}개 재호출" if args.retry_negatives and n_neg_cached else ""))

    sess = requests.Session()
    BATCH = 256
    done = reused = called = failed = wrote = neg = 0
    used_keys = set()   # 이번 런이 참조/기록한 캐시 키 → 끝에서 last_used_at 스탬프
    t0 = time.time()
    for i in range(0, len(targets), BATCH):
        batch = targets[i:i + BATCH]
        try:
            eids = [t[0] for t in batch]
            exc = load_excerpts(eng, bid, eids, args.max_chunks, args.max_text)

            results = {}   # eid -> (raw_desc, key, from_cache)
            todo = []      # (eid, name, key, user)
            for eid, name, norm in batch:
                excerpts = exc.get(eid, "")
                if not excerpts:
                    continue
                key = cache_key(norm, excerpts)
                used_keys.add(key)
                if key in cached:
                    results[eid] = (cached[key], key, True)
                    reused += 1
                else:
                    todo.append((eid, name, key, f"[엔티티]\n{name}\n\n[발췌]\n{excerpts}"))

            if todo:
                with ThreadPoolExecutor(max_workers=args.workers) as ex:
                    futs = {ex.submit(gemma, sess, args.gemma_url, args.gemma_key, args.gemma_model,
                                      SYSTEM_PROMPT, t[3]): t for t in todo}
                    for f in as_completed(futs):
                        eid, name, key, _ = futs[f]
                        try:
                            desc = f.result()
                        except Exception:
                            failed += 1
                            continue
                        results[eid] = (desc, key, False)
                        called += 1

            # 배치 커밋(체크포인트): description UPDATE(클린만) + 캐시 INSERT
            if results:
                with eng.begin() as c:
                    for eid, (desc, key, from_cache) in results.items():
                        cd = clean_desc(desc)
                        if cd is not None:
                            c.execute(text("UPDATE rag_graph_entities SET description=:d WHERE id=:e"),
                                      {"d": cd, "e": eid})
                            wrote += 1
                        else:
                            neg += 1   # '설명 불가' 등 → 컬럼 NULL 유지. 규모를 로그로 노출
                        if not from_cache:
                            # 저장 전 null 바이트 제거 — 원본을 그대로 넣으면 Postgres 가 거부해
                            # 배치 전체가 예외로 스킵된다(clean_desc 는 \x00 을 제거하지만 그
                            # 정제값을 저장하지 않았음).
                            # DO UPDATE: --retry-negatives 로 성공한 건이 옛 부정행을 덮어쓰도록.
                            c.execute(text(
                                "INSERT INTO rag_graph_summary_cache (cache_key, summary_kind, summary_text, model_name) "
                                "VALUES (:k, :kind, :s, :m) ON CONFLICT (cache_key) DO UPDATE SET "
                                "summary_text=EXCLUDED.summary_text, model_name=EXCLUDED.model_name"),
                                {"k": key, "kind": ENTITY_DESC_KIND,
                                 "s": (desc or "").replace("\x00", ""), "m": args.gemma_model})
                        cached[key] = desc
        except Exception as e:
            # 한 배치 실패가 스테이지·파이프라인 전체를 죽이지 않게 (스킵하고 계속)
            print(f"  [배치 {i} 실패, 스킵] {type(e).__name__}: {str(e)[:150]}", flush=True)
        done += len(batch)
        el = time.time() - t0
        rate = called / el if el else 0
        print(f"  [{done}/{len(targets)}] 재사용 {reused} / LLM {called} / 실패 {failed} / 기록 {wrote} "
              f"/ 설명불가 {neg} | {rate:.2f}콜/s, 경과 {el/60:.1f}m", flush=True)

    # 캐시 last_used_at 스탬프 — 미사용 행 회수(LRU) 판단 근거. 히트마다 UPDATE 하면
    # 14만 UPDATE/빌드가 되므로 런 끝에 1만 단위 배치로 한 번만 찍는다.
    if used_keys:
        keys = list(used_keys)
        with eng.begin() as c:
            for j in range(0, len(keys), 10000):
                c.execute(text("UPDATE rag_graph_summary_cache SET last_used_at=now() "
                               "WHERE cache_key = ANY(:ks)"), {"ks": keys[j:j + 10000]})

    print(f"[완료] 대상 {len(targets)} / 재사용 {reused} / 이번 LLM {called} / 실패 {failed} "
          f"/ description 기록 {wrote} / 설명불가 {neg} / last_used_at 스탬프 {len(used_keys)}")


if __name__ == "__main__":
    main()
