"""Graph Expansion k-hop 회수 (R-8) — 시드 엔티티에서 k-hop 확장 후 청크 회수.

graph_v2(1-hop, exp04서 vector에 패배)의 다중 hop 확장판. 기존 GLiNER2 공출현 그래프 사용(Full 추출 불요).
질문→엔티티 매칭(top_entities) → k-hop BFS 확장 → 확장 엔티티 등장 청크 → 질문 relevance 정렬 → top_k.
예상: hop 늘릴수록 후보 노이즈↑. exp04(1-hop 패배) 연장선.
"""
from typing import Dict, List, Set

from pipeline.shared.embedding import cosine
from .base import register


@register("graph_khop")
def retrieve(query_emb: List[float], top_k: int, *,
             chunk_emb: Dict[int, List[float]], graph: Dict, entity_emb: Dict[str, List[float]],
             top_entities: int = 12, hops: int = 2) -> List[int]:
    ent_scores = sorted(((cosine(query_emb, e), n) for n, e in entity_emb.items()), reverse=True)
    frontier: Set[str] = {n for _, n in ent_scores[:top_entities]}
    expanded: Set[str] = set(frontier)

    edges = graph.get("relation_edges") or graph.get("edges", [])
    adj: Dict[str, Set[str]] = {}
    for rel in edges:
        s, t = rel.get("source"), rel.get("target")
        if s is None or t is None:
            continue
        adj.setdefault(s, set()).add(t)
        adj.setdefault(t, set()).add(s)

    for _ in range(hops):
        nxt: Set[str] = set()
        for n in frontier:
            nxt |= adj.get(n, set())
        nxt -= expanded
        if not nxt:
            break
        expanded |= nxt
        frontier = nxt

    entity_chunks = graph.get("entity_chunks", {})
    cand: Set[int] = set()
    for e in expanded:
        cand.update(entity_chunks.get(e, []))
    scored = sorted(((cosine(query_emb, chunk_emb[ci]), ci) for ci in cand if ci in chunk_emb), reverse=True)
    return [ci for _, ci in scored[:top_k]]
