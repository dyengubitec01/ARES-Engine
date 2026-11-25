# -*- coding: utf-8 -*-
"""그래프RAG 검색 테스트 하니스 (우리 RDB+Qdrant 검증용, 운영 리트리버 아님).

흐름: 질의 → GLiNER2 엔티티추출 → 그래프노드 링킹(normalized 문자열매칭 + cosine 폴백)
      → 1-hop 이웃 확장 → 후보 엔티티 등장 청크 회수·랭킹.
비교: 같은 질의로 벡터 검색(rag_chunks_v1_dev) 나란히.

실행:
  .venv/Scripts/python.exe scripts/graph_build/test_retrieval.py
  .venv/Scripts/python.exe scripts/graph_build/test_retrieval.py --q "증평군 스마트도시 사업"
"""
from __future__ import annotations
import argparse, os, re, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import text, bindparam
from qdrant_client import QdrantClient
from config import settings
from embeddings.bge_m3_client import BGEM3Client
import build_graph as B

ENT_COLL = "rag_graph_entities_v1_dev"
CHUNK_COLL = "rag_chunks_v1_dev"
COS_TH = 0.85

DEFAULT_QUERIES = [
    "증평군 스마트도시 사업에 참여한 기관",
    "포항시 생활밀착형 도시재생 스마트 서비스",
    "스마트도시 관련 정부 부처",
]


def link_seeds(query, gliner, sch, eng, bid, emb, qc):
    """질의 엔티티 → 그래프노드 링킹 (문자열 우선, cosine 폴백)."""
    # 파일명 등 언더스코어/슬래시가 엔티티 경계를 가려 NER 실패 → 공백 정규화
    qn = re.sub(r"[_/\\]+", " ", query)
    spans = B.extract_spans(gliner, sch, qn)
    seeds = {}  # entity_id -> (name, how)
    with eng.connect() as c:
        for norm, surface, et in spans:
            row = c.execute(text("SELECT id, name FROM rag_graph_entities WHERE build_id=:b AND normalized_name=:n LIMIT 1"),
                            {"b": bid, "n": norm}).fetchone()
            if row:
                seeds[str(row[0])] = (row[1], "문자열")
                continue
            qv = emb.embed_texts([surface])[0]
            res = qc.query_points(collection_name=ENT_COLL, query=qv, limit=1).points
            if res and res[0].score >= COS_TH:
                seeds[res[0].payload["entity_id"]] = (res[0].payload["name"], f"cosine{res[0].score:.2f}")
    return seeds


def graph_search(eng, bid, seed_ids, k=5):
    if not seed_ids:
        return []
    with eng.connect() as c:
        # 1-hop 이웃 (weight 큰 순 상위 30)
        nq = text("SELECT (CASE WHEN source_entity_id IN :s THEN target_entity_id ELSE source_entity_id END) nb, weight "
                  "FROM rag_graph_edges WHERE build_id=:b AND (source_entity_id IN :s OR target_entity_id IN :s) "
                  "ORDER BY weight DESC LIMIT 30").bindparams(bindparam("s", expanding=True))
        nbrs = [str(r[0]) for r in c.execute(nq, {"b": bid, "s": seed_ids})]
        cands = list(set(seed_ids) | set(nbrs))
        # 청크 라우팅: 후보 엔티티 등장 청크, seed 가중치 3 / 이웃 1
        cq = text(
            "SELECT ec.chunk_id, ch.text, d.original_filename, "
            " sum(CASE WHEN ec.entity_id IN :seeds THEN 3 ELSE 1 END) score, count(*) hits "
            "FROM rag_graph_entity_chunks ec "
            "JOIN rag_chunks ch ON ec.chunk_id = ch.id "
            "JOIN doc_document_content d ON ch.doc_content_id = d.id "
            "WHERE ec.build_id=:b AND ec.entity_id IN :cands "
            "GROUP BY ec.chunk_id, ch.text, d.original_filename ORDER BY score DESC, hits DESC LIMIT :k"
        ).bindparams(bindparam("seeds", expanding=True), bindparam("cands", expanding=True))
        return list(c.execute(cq, {"b": bid, "seeds": seed_ids, "cands": cands, "k": k}))


def vector_search(emb, qc, query, k=5):
    qv = emb.embed_texts([query])[0]
    res = qc.query_points(collection_name=CHUNK_COLL, query=qv, limit=k).points
    out = []
    for r in res:
        pl = r.payload or {}
        out.append((pl.get("original_filename", "?"), (pl.get("text_for_search") or "")[:70], r.score))
    return out


def run_query(q, eng, bid, gliner, sch, emb, qc, k):
    """질의 1개 → 결과 라인 리스트."""
    out = []
    def p(s=""): out.append(str(s))
    p(f"■ 질의: {q}")
    seeds = link_seeds(q, gliner, sch, eng, bid, emb, qc)
    p("  링킹된 seed 엔티티: " + (", ".join(f"{n}({how})" for n, how in seeds.values()) or "없음"))
    p("  [그래프 회수]")
    for r in graph_search(eng, bid, list(seeds.keys()), k):
        p(f"    score={r[3]} hits={r[4]} | {r[2][:40]}")
        p(f"        {r[1][:70]!r}")
    p("  [벡터 회수]")
    for fn, snip, sc in vector_search(emb, qc, q, k):
        p(f"    cos={sc:.3f} | {fn[:40]}")
        p(f"        {snip!r}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", action="append", help="질의 (여러개 가능)")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--interactive", "-i", action="store_true", help="대화형 모드 (모델 1회 로드 후 계속 질문)")
    args = ap.parse_args()

    eng, db, schema = B.make_engine("dev")
    with eng.connect() as c:
        bid = c.execute(text("SELECT id FROM rag_graph_builds WHERE status='active' ORDER BY id DESC LIMIT 1")).scalar()

    print("모델 로드 중...")
    from gliner2 import GLiNER2
    gliner = GLiNER2.from_pretrained(B.MODEL_NAME)
    sch = gliner.create_schema().entities(B.ENTITY_LABELS)
    emb = BGEM3Client()
    qc = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, timeout=60)
    print(f"준비 완료 (build {bid}, dev).")

    if args.interactive:
        print("대화형 모드 — 질문 입력 (빈 줄 또는 Ctrl+C 종료)\n")
        while True:
            try:
                q = input("질의> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n종료"); break
            if not q:
                print("종료"); break
            print("\n".join(run_query(q, eng, bid, gliner, sch, emb, qc, args.k)))
            print()
        return

    queries = args.q or DEFAULT_QUERIES
    L = [f"=== 그래프RAG 검색 테스트 (build {bid}, dev) ===", ""]
    for q in queries:
        L += run_query(q, eng, bid, gliner, sch, emb, qc, args.k) + [""]
    with io.open(r"c:\tmp\test_retrieval.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("saved c:\\tmp\\test_retrieval.txt")


if __name__ == "__main__":
    main()
