"""Vector top-k 회수 — 임베딩 cosine 유사도 정렬.

이전: scripts/graph_rag_poc/_shared/lazy_value_test/eval_retrieval.py: retrieve_vector
"""
from typing import Dict, List

from pipeline.shared.embedding import cosine
from .base import register


@register("vector_topk")
def retrieve(query_emb: List[float], top_k: int, *, chunk_emb: Dict[int, List[float]],
             max_index: int = None) -> List[int]:
    """query 임베딩 ↔ 청크 임베딩 cosine → top_k 청크 인덱스(내림차순).

    max_index 지정 시 chunk_index >= max_index 청크 제외(RAPTOR 요약 pseudo-chunk 배제용).
    """
    items = chunk_emb.items() if max_index is None else (
        (ci, e) for ci, e in chunk_emb.items() if ci < max_index)
    scored = sorted(((cosine(query_emb, e), ci) for ci, e in items), reverse=True)
    return [ci for _, ci in scored[:top_k]]
