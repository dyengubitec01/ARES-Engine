"""vector + graph 통합 회수 — 벡터 검색 ∪ 그래프 순회 (always-both, 라우팅 없음).

운영 벡터RAG에 그래프RAG를 '더하는' 통합. 질문마다 벡터·그래프 둘 다 태워 후보를 합침.
  - 벡터 top_k = 전역 cosine 상위 청크 (기존 강점 유지)
  - 그래프 top_k = 순회(linking+neighborhood+path+community)가 찾은 관계/이웃 청크 (추가분)
합집합을 그대로 반환 — cosine로 재정렬·절단하지 않음(절단하면 그래프 추가분이 벡터에 밀려 사라짐).
이후 relevance_filter(LLM)가 관련 청크만 선별 → 그래프가 살린 관계 청크가 답변에 반영될 기회.
"""
from typing import Dict, List

from .base import register
from .vector_topk import retrieve as _vector
from .graph_rag import retrieve as _graph


@register("vector_plus_graph")
def retrieve(query_emb: List[float], top_k: int, *,
             chunk_emb: Dict[int, List[float]], graph: Dict, entity_emb: Dict[str, List[float]],
             query_text: str = None, top_entities: int = 6, hops: int = 1, max_path_len: int = 3,
             use_community: bool = False, max_index: int = None) -> List[int]:
    v = _vector(query_emb, top_k, chunk_emb=chunk_emb, max_index=max_index)
    g = _graph(query_emb, top_k, chunk_emb=chunk_emb, graph=graph, entity_emb=entity_emb,
               query_text=query_text, top_entities=top_entities, hops=hops, max_path_len=max_path_len,
               use_community=use_community)
    seen, pool = set(), []
    for ci in list(v) + list(g):   # 벡터 우선, 그래프 추가분 뒤에
        if ci not in seen:
            seen.add(ci)
            pool.append(ci)
    return pool
