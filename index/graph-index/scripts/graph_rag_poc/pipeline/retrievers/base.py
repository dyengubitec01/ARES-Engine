"""Retriever 공통 인터페이스.

각 retriever는 함수 형태 retrieve(query_emb, top_k, **state) -> list[chunk_index]를 export.
state는 retriever별 초기화 데이터(chunk_emb, graph 등)를 의미.

Phase 5 runner는 RETRIEVERS registry로 type → 함수 매핑.
"""
from typing import Callable, Dict


# Phase 5 runner가 채울 registry. retriever 모듈은 import 시 자기 등록.
RETRIEVERS: Dict[str, Callable] = {}


def register(name: str):
    """데코레이터: 함수를 registry에 등록.

    @register("vector_topk")
    def retrieve(q_emb, top_k, *, chunk_emb): ...
    """
    def wrap(fn):
        RETRIEVERS[name] = fn
        return fn
    return wrap
