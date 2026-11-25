"""BGE-M3 임베딩 + 청크·엔티티 임베딩 헬퍼.

이전:
- scripts/graph_rag_poc/_shared/common_query.py: embed_query_dense
- scripts/graph_rag_poc/_shared/lazy_value_test/eval_retrieval.py:
    cosine, embed_chunks, embed_entities
"""
import math
import time
from typing import Dict, List

import requests

from .config import Config as C


def embed_query_dense(query: str, _tries: int = 4) -> List[float]:
    """단일 텍스트 → BGE-M3 dense 임베딩.

    localhost 간헐 timeout 대비 재시도(backoff). 성공 시 동작 불변, 실패 시에만 재시도.
    """
    last = None
    for i in range(_tries):
        try:
            r = requests.post(
                C.BGE_M3_API_URL,
                json={"model": C.BGE_M3_MODEL, "input": query},
                headers={"Authorization": f"Bearer {C.BGE_M3_API_KEY}"},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()["data"][0]["embedding"]
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last


def embed_chunks(chunks: List[Dict]) -> Dict[int, List[float]]:
    """각 청크 텍스트 → chunk_index 키 dict."""
    return {c["chunk_index"]: embed_query_dense(c["text"]) for c in chunks}


def embed_entities(graph: Dict) -> Dict[str, List[float]]:
    """그래프의 entity_chunks 키(=엔티티명) → 엔티티명 자체 텍스트의 임베딩.

    LightRAG/HippoRAG 등에서 description이 있으면 description을 임베딩하지만,
    Lazy 그래프엔 description이 없으니 엔티티 이름 자체로 임베딩.
    """
    entity_chunks = graph.get("entity_chunks", {})
    out: Dict[str, List[float]] = {}
    for name in entity_chunks.keys():
        text = name
        out[name] = embed_query_dense(text)
    return out


def cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb + 1e-9)
