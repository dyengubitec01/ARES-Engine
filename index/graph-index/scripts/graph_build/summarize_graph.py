# -*- coding: utf-8 -*-
"""그래프 LLM 요약 레이어 (increment: gemma4 호출) — 관계/커뮤니티 요약 생성.

active 빌드의 상위 엣지/커뮤니티에 대해 gemma4(클라우드 API)로 요약 생성 후
rag_graph_edges.relation_summary / rag_graph_communities.summary 에 저장.
구조 빌드(build_graph) 후 얹는 층. 리소스 절약 위해 상위 N개만(테스트).

실행:
  .venv/Scripts/python.exe scripts/graph_build/summarize_graph.py --db dev \
     --gemma-url http://localhost:8000 \
     --gemma-key sk-... --max-edges 5 --min-community-size 3
"""
from __future__ import annotations
import argparse, os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import requests
from sqlalchemy import create_engine, text
from config import settings


def make_engine(db):
    schema = "rag_dev" if db == "dev" else settings.postgres_schema
    dbname = "ragdb_dev" if db == "dev" else settings.postgres_db
    url = (f"postgresql://{settings.postgres_user}:{quote_plus(settings.postgres_password)}"
           f"@{settings.postgres_host}:{settings.postgres_port}/{dbname}")
    return create_engine(url, connect_args={"options": f"-csearch_path={schema},public"})


def gemma(url, key, model, prompt, max_tokens=160, max_retries=4):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = {"model": model, "temperature": 0, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]}
    endpoint = url.rstrip("/") + "/v1/chat/completions"
    last = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(endpoint, json=body, headers=headers, timeout=120)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.RequestException as e:
            last = e
            if attempt == max_retries:
                break
            time.sleep(min(2 ** attempt, 20))  # 2,4,8,16 — 일시 네트워크 blip/서버 재시작 대비
    raise last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="dev")
    ap.add_argument("--gemma-url", default=os.getenv("GEMMA_API_URL"))
    ap.add_argument("--gemma-key", default=os.getenv("GEMMA_API_KEY", ""))
    ap.add_argument("--gemma-model", default="gemma-4-31b")
    ap.add_argument("--max-edges", type=int, default=5)
    ap.add_argument("--min-community-size", type=int, default=3,
                    help="이 엔티티 수 이상 커뮤니티만 요약(임계값, 상한 없음). "
                         "1=혼자·2=단일관계(라벨 몫) 제외, 3+=작은 그룹(요약 대상)")
    ap.add_argument("--workers", type=int, default=32, help="동시 gemma 호출 수(병렬)")
    args = ap.parse_args()
    if not args.gemma_url:
        raise SystemExit("--gemma-url 필요")

    eng = make_engine(args.db)
    with eng.connect() as c:
        bid = c.execute(text("SELECT id FROM rag_graph_builds WHERE status='active' ORDER BY id DESC LIMIT 1")).scalar()
    print(f"[active build {bid}] 관계요약 {args.max_edges}개 + 커뮤니티요약(엔티티>={args.min_community_size}) 생성\n")

    # ── 관계 요약 (weight 상위 엣지) — 발췌 수집(순차) → gemma(병렬) → 배치 저장 ──
    print("=== 관계 요약 (relation_summary) ===")
    rel_inputs = []  # (eid, prompt)
    rel_meta = {}    # eid -> (sname, tname, weight) — 로그 출력용
    with eng.connect() as c:
        c.execute(text("SET max_parallel_workers_per_gather = 0"))  # 발췌쿼리 DSM 회피
        edges = c.execute(text(
            "SELECT e.id, s.id, t.id, s.name, t.name, e.weight "
            "FROM rag_graph_edges e "
            "JOIN rag_graph_entities s ON e.source_entity_id=s.id "
            "JOIN rag_graph_entities t ON e.target_entity_id=t.id "
            "WHERE e.build_id=:b ORDER BY e.weight DESC LIMIT :n"), {"b": bid, "n": args.max_edges}).fetchall()
        for eid, sid, tid, sname, tname, w in edges:
            chunks = [r[0] for r in c.execute(text(
                "SELECT ch.text FROM rag_chunks ch WHERE ch.id IN ("
                " SELECT chunk_id FROM rag_graph_entity_chunks WHERE build_id=:b AND entity_id=:s"
                " INTERSECT "
                " SELECT chunk_id FROM rag_graph_entity_chunks WHERE build_id=:b AND entity_id=:t) LIMIT 3"),
                {"b": bid, "s": sid, "t": tid}).fetchall()]
            excerpt = "\n---\n".join(t[:400] for t in chunks)
            rel_inputs.append((eid, f"다음 문서 발췌를 근거로 '{sname}'와(과) '{tname}'의 관계를 한 문장으로 요약해줘. "
                                    f"근거가 불충분하면 '관계 불명확'이라고만 답해.\n\n발췌:\n{excerpt}"))
            rel_meta[eid] = (sname, tname, w)
    rel_rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(gemma, args.gemma_url, args.gemma_key, args.gemma_model, p): eid for eid, p in rel_inputs}
        for f in as_completed(futs):
            try:
                rel_rows.append((futs[f], f.result()))
            except Exception as e:
                print(f"  [관계요약 1건 실패] {type(e).__name__}: {str(e)[:100]}")
    with eng.begin() as c:
        for eid, summary in rel_rows:
            c.execute(text("UPDATE rag_graph_edges SET relation_summary=:s WHERE id=:e"), {"s": summary, "e": eid})
    for eid, summary in sorted(rel_rows, key=lambda x: -rel_meta[x[0]][2]):
        sn, tn, w = rel_meta[eid]
        print(f"  [{sn} ~ {tn} (w={w:.0f})] → {summary}")
    print(f"  → 관계요약 {len(rel_rows)}/{len(edges)} 완료")

    # ── 커뮤니티 요약 (임계값 이상 전부) — 입력 수집(순차) → gemma(병렬) → 배치 저장 ──
    print("=== 커뮤니티 요약 (summary) ===")
    com_inputs = []  # (cid, prompt)
    com_meta = {}    # cid -> (ecount, names[:6]) — 로그 출력용
    with eng.connect() as c:
        c.execute(text("SET max_parallel_workers_per_gather = 0"))  # 발췌쿼리 DSM(/dev/shm 64MB) 회피
        comms = c.execute(text(
            "SELECT id, entity_count FROM rag_graph_communities WHERE build_id=:b "
            "AND entity_count >= :ms ORDER BY entity_count DESC"),
            {"b": bid, "ms": args.min_community_size}).fetchall()
        print(f"  대상 {len(comms)}개 (엔티티 >= {args.min_community_size}, 상한 없음, workers={args.workers}) — 발췌 수집중...", flush=True)
        for i, (cid, ecount) in enumerate(comms):
            rows = c.execute(text(
                "SELECT id, name FROM rag_graph_entities WHERE build_id=:b AND community_id=:c "
                "ORDER BY chunk_count DESC LIMIT 12"), {"b": bid, "c": cid}).fetchall()
            names = [r[1] for r in rows]
            top_ids = [str(r[0]) for r in rows]
            # 발췌 = 대표(고빈도) 엔티티 12개의 청크. SQL DISTINCT는 수만행을 dedupe하느라 느림(63s)
            # → DISTINCT 빼고 LIMIT 20으로 몇 개만 뽑아 Python에서 중복제거(3개) → 0.02s.
            raw = [r[0] for r in c.execute(text(
                "SELECT ch.text FROM rag_chunks ch "
                "JOIN rag_graph_entity_chunks ec ON ch.id = ec.chunk_id "
                "WHERE ec.build_id=:b AND ec.entity_id = ANY(CAST(:ids AS uuid[])) LIMIT 20"),
                {"b": bid, "ids": top_ids}).fetchall()] if top_ids else []
            seen = []
            for t in raw:
                if t and t not in seen:
                    seen.append(t)
                if len(seen) >= 3:
                    break
            excerpt = "\n---\n".join(t[:300] for t in seen)
            com_inputs.append((cid, f"다음 엔티티들과 문서 발췌가 한 그룹으로 묶였어. 이 그룹의 공통 주제를 한 문장으로 요약해줘.\n\n"
                                    f"엔티티: {', '.join(names)}\n\n발췌:\n{excerpt}"))
            com_meta[cid] = (ecount, names[:6])
            if (i + 1) % 50 == 0:
                print(f"    발췌 수집 {i+1}/{len(comms)}", flush=True)
    com_rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(gemma, args.gemma_url, args.gemma_key, args.gemma_model, p): cid for cid, p in com_inputs}
        for f in as_completed(futs):
            try:
                com_rows.append((futs[f], f.result()))
            except Exception as e:
                print(f"  [커뮤니티요약 1건 실패] {type(e).__name__}: {str(e)[:100]}")
    with eng.begin() as c:
        for cid, summary in com_rows:
            c.execute(text("UPDATE rag_graph_communities SET summary=:s WHERE id=:c"), {"s": summary, "c": cid})
    print("  --- 커뮤니티 요약 결과 (큰 것부터) ---")
    for cid, summary in sorted(com_rows, key=lambda x: -com_meta[x[0]][0]):
        ec, names6 = com_meta[cid]
        print(f"  [size={ec}] 멤버: {', '.join(names6)}...\n    → {summary}")
    print(f"  → 커뮤니티요약 {len(com_rows)}/{len(comms)} 완료")

    print("[완료] DB에 relation_summary / summary 저장됨")


if __name__ == "__main__":
    main()
