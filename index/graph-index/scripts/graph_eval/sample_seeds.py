# -*- coding: utf-8 -*-
"""골든셋 시드 샘플러 (그래프-시드 + 청크-근거).

active 그래프 빌드에서 4유형 시드를 뽑고, 각 시드의 '근거 청크' 텍스트까지 회수한다.
LLM은 안 부른다 — 이 산출물(seeds.json)을 다음 단계(generate_golden.py)가 받아
청크를 근거로 질문/정답을 만든다. 순환편향 방지: 질문 시드는 그래프에서,
정답 근거는 실제 청크(원본 문서)에 고정.

4유형(파일럿 기본 각 10):
  relation   = 관계추론  : relation_label 있는 고-weight 엣지 → 양끝 엔티티 공출현 청크
  synthesis  = 엔티티종합: 여러 청크 등장하는 의미있는(설명有) 엔티티 → 등장 청크 다수
  sensemaking= 광범위    : summary 있는 커뮤니티(엔티티≥5) → 멤버 엔티티 대표 청크
  control    = 벡터충분  : 단일/소수 청크 엔티티 → 청크 1개(단일 사실)

실행:
  .venv/Scripts/python.exe scripts/graph_eval/sample_seeds.py            # active 빌드, 각 10개
  .venv/Scripts/python.exe scripts/graph_eval/sample_seeds.py --per-type 5 --build 15
"""
from __future__ import annotations
import argparse
import json
import os
import random
import sys
from urllib.parse import quote_plus

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import create_engine, text, bindparam
from config import settings

# 근거 청크 텍스트 최대 길이(LLM 프롬프트 비용 억제). 너무 긴 청크는 앞부분만.
CHUNK_TEXT_CAP = 1400
MAX_CHUNKS_PER_SEED = 4  # synthesis/sensemaking에서 근거로 담을 최대 청크 수

# 도메인 한정 필터(사용자 결정 2026-07-06): 스마트시티 구축계획서 한 종류로 통일.
# 코퍼스는 실제로 ①스마트도시계획(75문서/51k청크) ②도로/교통·인프라 설계·규격(설계서·시방서·
# 품셈·철도규격·공항·보안, 939문서) 두 갈래. 표 제외만으론 ②(산문)가 남아 오프도메인 유발 →
# 파일명에 '스마트도시계획'/'스마트시티계획' 있는 도시 마스터플랜만 포함. doc 별칭 d 기준.
DOMAIN_FILTER = (
    "(d.original_filename LIKE '%스마트도시계획%' OR d.original_filename LIKE '%스마트시티계획%')"
)


def is_noisy_chunk(t: str) -> bool:
    """산문 문서 안에도 남는 표/수량산출 청크 걸러내기. 파이프·#N/A·숫자비율 신호."""
    if not t or len(t) < 40:
        return True
    if t.count("|") > 12 or "#N/A" in t or "#VALUE" in t:
        return True
    digits = sum(ch.isdigit() for ch in t)
    if digits / max(len(t), 1) > 0.35:
        return True
    return False


def make_engine():
    """prod(rag 스키마/ragdb) 엔진. .env가 이미 prod를 가리킴(host=localhost)."""
    url = (f"postgresql://{settings.postgres_user}:{quote_plus(settings.postgres_password)}"
           f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    return create_engine(url, connect_args={"options": f"-csearch_path={settings.postgres_schema},public"})


def active_build(c) -> int:
    return c.execute(text(
        "SELECT id FROM rag_graph_builds WHERE status='active' ORDER BY id DESC LIMIT 1")).scalar()


def fetch_chunk_texts(c, chunk_ids):
    """chunk_id → 정제된 근거 청크만 반환. 스마트시티계획 문서(DOMAIN_FILTER) + 비노이즈 청크 한정."""
    if not chunk_ids:
        return {}
    q = text(
        "SELECT ch.id, ch.chunk_index, d.original_filename, ch.text "
        "FROM rag_chunks ch JOIN doc_document_content d ON ch.doc_content_id=d.id "
        f"WHERE ch.id IN :ids AND {DOMAIN_FILTER}").bindparams(bindparam("ids", expanding=True))
    out = {}
    for cid, idx, fname, txt in c.execute(q, {"ids": [str(x) for x in chunk_ids]}):
        t = (txt or "").strip()
        if is_noisy_chunk(t):
            continue
        if len(t) > CHUNK_TEXT_CAP:
            t = t[:CHUNK_TEXT_CAP] + " …"
        out[str(cid)] = {"chunk_index": idx, "filename": fname, "text": t}
    return out


# ────────────────────────────── 유형별 시드 ──────────────────────────────

# 단독으로도 제네릭한 관계 라벨(구체적 근거 안 됨).
GENERIC_LABELS = {"접함", "협력", "포함", "관련", "연관", "인접", "함께", "동일", "유사",
                  "구성", "기반", "반영", "사용", "적용", "활용", "제공", "연계", "연동"}


def seeds_relation(c, bid, n, pool_mult=80):
    """관계추론: 단일·구체 라벨 + 중간빈도 엔티티(허브 제외). 근거=양끝 공출현 산문 청크."""
    rows = c.execute(text(
        "SELECT e.id, s.id, t.id, s.name, t.name, e.weight, e.relation_label "
        "FROM rag_graph_edges e "
        "JOIN rag_graph_entities s ON e.source_entity_id=s.id "
        "JOIN rag_graph_entities t ON e.target_entity_id=t.id "
        "WHERE e.build_id=:b AND e.relation_label IS NOT NULL "
        "  AND s.chunk_count BETWEEN 3 AND 60 AND t.chunk_count BETWEEN 3 AND 60 "
        "ORDER BY e.weight DESC LIMIT :lim"),
        {"b": bid, "lim": n * pool_mult}).fetchall()

    def good_label(lb):
        lb = (lb or "").strip()
        # 콤마나열 = 메가허브 제네릭 / 단독 제네릭어 / 과도한 길이 제외
        return lb and ("," not in lb) and (lb not in GENERIC_LABELS) and (len(lb) <= 12)

    cand = [r for r in rows if good_label(r[6])]
    random.shuffle(cand)
    seeds = []
    for eid, sid, tid, sname, tname, w, label in cand:
        if len(seeds) >= n:
            break
        # 공출현 청크(양끝 엔티티가 함께 등장) — 관계의 실제 근거. 넉넉히 뽑아 산문/비노이즈로 정제.
        shared = [str(x[0]) for x in c.execute(text(
            "SELECT chunk_id FROM rag_graph_entity_chunks WHERE build_id=:b AND entity_id=:s "
            "INTERSECT "
            "SELECT chunk_id FROM rag_graph_entity_chunks WHERE build_id=:b AND entity_id=:t "
            "LIMIT 12"), {"b": bid, "s": sid, "t": tid}).fetchall()]
        texts = fetch_chunk_texts(c, shared)
        if not texts:
            continue
        keep = dict(list(texts.items())[:MAX_CHUNKS_PER_SEED])
        seeds.append({
            "type": "relation",
            "seed": {"source": sname, "target": tname, "relation_label": label, "weight": w},
            "required_chunk_ids": list(keep.keys()),
            "evidence_chunks": list(keep.values()),
        })
    return seeds


def seeds_synthesis(c, bid, n, pool_mult=40):
    """엔티티종합: 여러 청크에 등장하는 의미있는(description 有) 엔티티. 근거=등장 청크 다수."""
    # 중간빈도(4~25) 밴드: 상한(40)에 몰리는 제네릭·표 엔티티 회피. 밴드 내 랜덤분산.
    rows = c.execute(text(
        "SELECT id, name, entity_type, chunk_count, description FROM rag_graph_entities "
        "WHERE build_id=:b AND description IS NOT NULL "
        "  AND chunk_count BETWEEN 4 AND 25 "
        "ORDER BY chunk_count DESC LIMIT :lim"),
        {"b": bid, "lim": n * pool_mult}).fetchall()
    cand = list(rows)
    random.shuffle(cand)
    seeds = []
    for eid, name, etype, cc, desc in cand:
        if len(seeds) >= n:
            break
        chunk_ids = [str(x[0]) for x in c.execute(text(
            "SELECT chunk_id FROM rag_graph_entity_chunks WHERE build_id=:b AND entity_id=:e "
            "ORDER BY occurrence_count DESC LIMIT 12"),
            {"b": bid, "e": eid}).fetchall()]
        texts = dict(list(fetch_chunk_texts(c, chunk_ids).items())[:MAX_CHUNKS_PER_SEED])
        if len(texts) < 2:  # 종합이려면 최소 2 산문청크
            continue
        seeds.append({
            "type": "synthesis",
            "seed": {"entity": name, "entity_type": etype, "chunk_count": cc, "description": desc},
            "required_chunk_ids": list(texts.keys()),
            "evidence_chunks": list(texts.values()),
        })
    return seeds


def seeds_sensemaking(c, bid, n, pool_mult=20):
    """광범위: summary 있는 커뮤니티(엔티티≥5). 근거=멤버 엔티티 대표 청크 샘플."""
    # 중간 크기(5~60) 커뮤니티만: 엔티티 수천개 거대군집은 주제 응집이 없어 제외.
    rows = c.execute(text(
        "SELECT id, label, summary, entity_count FROM rag_graph_communities "
        "WHERE build_id=:b AND summary IS NOT NULL AND entity_count BETWEEN 5 AND 60 "
        "ORDER BY entity_count DESC LIMIT :lim"),
        {"b": bid, "lim": n * pool_mult}).fetchall()
    cand = list(rows)
    random.shuffle(cand)
    seeds = []
    for comm_id, label, summary, ecnt in cand:
        if len(seeds) >= n:
            break
        # 멤버 엔티티들의 청크 여럿 → 산문/비노이즈로 정제 후 대표 근거로
        chunk_ids = [str(x[0]) for x in c.execute(text(
            "SELECT DISTINCT ec.chunk_id FROM rag_graph_entity_chunks ec "
            "JOIN rag_graph_entities e ON ec.entity_id=e.id "
            "WHERE e.build_id=:b AND e.community_id=:cid "
            "LIMIT 20"),
            {"b": bid, "cid": comm_id}).fetchall()]
        members = [x[0] for x in c.execute(text(
            "SELECT name FROM rag_graph_entities WHERE build_id=:b AND community_id=:cid "
            "ORDER BY chunk_count DESC LIMIT 10"), {"b": bid, "cid": comm_id}).fetchall()]
        texts = dict(list(fetch_chunk_texts(c, chunk_ids).items())[:MAX_CHUNKS_PER_SEED])
        if len(texts) < 2:
            continue
        seeds.append({
            "type": "sensemaking",
            "seed": {"community_label": label, "summary": summary,
                     "entity_count": ecnt, "members": members},
            "required_chunk_ids": list(texts.keys()),
            "evidence_chunks": list(texts.values()),
        })
    return seeds


def seeds_control(c, bid, n, pool_mult=100):
    """벡터충분: 소수 청크(2~8)의 정제된 엔티티 → 산문 청크 1개(단일 사실 회수).
    단일청크(chunk_count=1) 롱테일은 OCR 파편(소르셔·OCTB류)이 많아 제외."""
    rows = c.execute(text(
        "SELECT id, name, entity_type, chunk_count FROM rag_graph_entities "
        "WHERE build_id=:b AND chunk_count BETWEEN 2 AND 8 "
        "  AND char_length(name) BETWEEN 2 AND 20 AND name ~ '[가-힣]' "
        "LIMIT :lim"),
        {"b": bid, "lim": n * pool_mult}).fetchall()
    cand = list(rows)
    random.shuffle(cand)
    seeds = []
    for eid, name, etype, cc in cand:
        if len(seeds) >= n:
            break
        chunk_ids = [str(x[0]) for x in c.execute(text(
            "SELECT chunk_id FROM rag_graph_entity_chunks WHERE build_id=:b AND entity_id=:e LIMIT 6"),
            {"b": bid, "e": eid}).fetchall()]
        texts = dict(list(fetch_chunk_texts(c, chunk_ids).items())[:1])  # 단일 사실 → 1청크
        if not texts:
            continue
        seeds.append({
            "type": "control",
            "seed": {"entity": name, "entity_type": etype, "chunk_count": cc},
            "required_chunk_ids": list(texts.keys()),
            "evidence_chunks": list(texts.values()),
        })
    return seeds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-type", type=int, default=10, help="유형별 시드 개수(기본 10)")
    ap.add_argument("--build", type=int, default=0, help="빌드 id 지정(기본 active)")
    ap.add_argument("--seed", type=int, default=42, help="샘플링 랜덤시드(재현용)")
    ap.add_argument("--out", default=None, help="출력 경로(기본 data/qa/seeds_build{N}.json)")
    args = ap.parse_args()
    random.seed(args.seed)

    eng = make_engine()
    with eng.connect() as c:
        c.execute(text("SET max_parallel_workers_per_gather = 0"))  # 발췌쿼리 DSM 회피(dev 메모리)
        bid = args.build or active_build(c)
        b = c.execute(text("SELECT corpus_chunk_count, entity_count, edge_count, community_count, status "
                           "FROM rag_graph_builds WHERE id=:b"), {"b": bid}).fetchone()
        print(f"[build {bid}] status={b[4]} 청크{b[0]} 엔티티{b[1]} 엣지{b[2]} 커뮤니티{b[3]}")
        print(f"유형별 {args.per_type}개 샘플링...\n")

        groups = {
            "relation": seeds_relation(c, bid, args.per_type),
            "synthesis": seeds_synthesis(c, bid, args.per_type),
            "sensemaking": seeds_sensemaking(c, bid, args.per_type),
            "control": seeds_control(c, bid, args.per_type),
        }

    all_seeds = []
    for k, v in groups.items():
        print(f"  {k:12s} {len(v)}/{args.per_type}")
        all_seeds.extend(v)

    out_path = args.out or os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "graph_rag_poc", "data", "qa", f"seeds_build{bid}.json"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    payload = {"build_id": bid, "per_type": args.per_type, "random_seed": args.seed,
               "total": len(all_seeds), "seeds": all_seeds}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n총 {len(all_seeds)}개 시드 → {out_path}")


if __name__ == "__main__":
    sys.exit(main() or 0)
