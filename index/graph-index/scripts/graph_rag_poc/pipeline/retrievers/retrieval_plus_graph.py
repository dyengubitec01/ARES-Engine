"""R-2/R-3/R-6 검색기를 graph_rag와 union (그래프 통합 프레임에서 격리 테스트용).

각 = (해당 검색 확장) ∪ (graph_rag 엔티티 순회). relevance_filter가 이후 좁힘.
- hybrid_plus_graph    : R-2 (BM25+dense) ∪ graph
- dual_plus_graph      : R-3 (low/high 키워드) ∪ graph
- multistage_plus_graph: R-6 (dense→BM25 재정렬) ∪ graph
"""
from typing import Dict, List

from .base import register
from .graph_rag import retrieve as _graph
from .hybrid import retrieve as _hybrid
from .dual_level import retrieve as _dual
from .multistage import retrieve as _multistage


def _union(a, b, chunk_emb):
    seen, pool = set(), []
    for ci in list(a) + list(b):
        if ci not in seen and ci in chunk_emb:
            seen.add(ci)
            pool.append(ci)
    return pool


def _g(query_emb, top_k, chunk_emb, graph, entity_emb, query_text):
    return _graph(query_emb, top_k, chunk_emb=chunk_emb, graph=graph, entity_emb=entity_emb, query_text=query_text)


@register("hybrid_plus_graph")
def hybrid_plus_graph(query_emb: List[float], top_k: int, *, chunk_emb, bm25, query_text,
                      graph, entity_emb, alpha: float = 0.7) -> List[int]:
    h = _hybrid(query_emb, top_k, chunk_emb=chunk_emb, bm25=bm25, query_text=query_text, alpha=alpha)
    return _union(h, _g(query_emb, top_k, chunk_emb, graph, entity_emb, query_text), chunk_emb)


@register("dual_plus_graph")
def dual_plus_graph(query_emb: List[float], top_k: int, *, chunk_emb, query_text,
                    graph, entity_emb, low_high_k: int = 8) -> List[int]:
    h = _dual(query_emb, top_k, chunk_emb=chunk_emb, query_text=query_text, low_high_k=low_high_k)
    return _union(h, _g(query_emb, top_k, chunk_emb, graph, entity_emb, query_text), chunk_emb)


@register("multistage_plus_graph")
def multistage_plus_graph(query_emb: List[float], top_k: int, *, chunk_emb, bm25, query_text,
                          graph, entity_emb, stage1_k: int = 30) -> List[int]:
    h = _multistage(query_emb, top_k, chunk_emb=chunk_emb, bm25=bm25, query_text=query_text, stage1_k=stage1_k)
    return _union(h, _g(query_emb, top_k, chunk_emb, graph, entity_emb, query_text), chunk_emb)
