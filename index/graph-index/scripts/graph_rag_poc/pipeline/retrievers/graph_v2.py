"""그래프 v2 회수 — 엔티티 임베딩 매칭 + 1-hop 확장 + relevance ranking.

이전: scripts/graph_rag_poc/_shared/lazy_value_test/eval_retrieval.py: retrieve_graph_v2

알고리즘:
1. 질문 임베딩과 엔티티 임베딩 cosine → top_entities개 엔티티 선택
2. 그래프 엣지(relation_edges 우선, 없으면 공출현 edges)로 1-hop 확장
3. 확장된 엔티티들이 등장하는 청크 합집합 = 후보 풀
4. 후보 풀을 질문 임베딩 cosine으로 재정렬 → top_k 반환

1000청크 측정 결과: vector_topk와 recall@20 동일(0.83=0.83). 자기완결적 청크 도메인에선 그래프 라우팅이 추가 회수 없음.
"""
from typing import Dict, List, Set

from pipeline.shared.embedding import cosine
from .base import register


@register("graph_v2")
def retrieve(query_emb: List[float], top_k: int, *,
             chunk_emb: Dict[int, List[float]],
             graph: Dict,
             entity_emb: Dict[str, List[float]],
             top_entities: int = 12) -> List[int]:
    """그래프 기반 후보 선정 + cosine 정렬."""
    # 1. 엔티티 임베딩 매칭 top-K
    ent_scores = sorted(
        ((cosine(query_emb, e), n) for n, e in entity_emb.items()),
        reverse=True,
    )
    top_ents: Set[str] = {n for _, n in ent_scores[:top_entities]}

    # 2. 관계 1-hop 확장 (relation_edges 우선, Lazy는 공출현 edges)
    rel_edges = graph.get("relation_edges") or graph.get("edges", [])
    expanded: Set[str] = set(top_ents)
    for rel in rel_edges:
        if rel["source"] in top_ents:
            expanded.add(rel["target"])
        if rel["target"] in top_ents:
            expanded.add(rel["source"])

    # 3. 후보 청크 = 확장 엔티티가 등장하는 청크
    entity_chunks = graph.get("entity_chunks", {})
    candidate: Set[int] = set()
    for e in expanded:
        candidate.update(entity_chunks.get(e, []))

    # 4. 후보 청크를 질문 relevance로 ranking
    scored = sorted(
        ((cosine(query_emb, chunk_emb[ci]), ci) for ci in candidate if ci in chunk_emb),
        reverse=True,
    )
    return [ci for _, ci in scored[:top_k]]
