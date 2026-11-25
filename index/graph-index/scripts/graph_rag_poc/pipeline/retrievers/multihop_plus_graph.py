"""multihop + graph 통합 회수 — R-5(LLM followup 재검색) ∪ graph_rag(엔티티 순회).

multihop 자체가 1차 dense(=vector) 포함 → 이 union = vector + LLM-followup + 엔티티traversal 전부.
두 확장 메커니즘이 직교(R-5=질문기반 LLM 재검색 / graph=엔티티 구조) → 보완 기대.
relevance_filter가 이후 좁힘.
"""
from typing import Dict, List

from .base import register
from .multihop import retrieve as _mh
from .graph_rag import retrieve as _graph


@register("multihop_plus_graph")
def retrieve(query_emb: List[float], top_k: int, *,
             chunk_emb: Dict[int, List[float]], graph: Dict, entity_emb: Dict[str, List[float]],
             query_text: str, chunks_db: Dict[int, Dict], hop2_k: int = 5,
             top_entities: int = 6, hops: int = 1, max_path_len: int = 3,
             use_community: bool = False) -> List[int]:
    mh = _mh(query_emb, top_k, chunk_emb=chunk_emb, query_text=query_text, chunks_db=chunks_db, hop2_k=hop2_k)
    g = _graph(query_emb, top_k, chunk_emb=chunk_emb, graph=graph, entity_emb=entity_emb, query_text=query_text,
               top_entities=top_entities, hops=hops, max_path_len=max_path_len, use_community=use_community)
    seen, pool = set(), []
    for ci in list(mh) + list(g):   # multihop(=vector포함) 우선, 그래프 추가분 뒤
        if ci not in seen:
            seen.add(ci)
            pool.append(ci)
    return pool
