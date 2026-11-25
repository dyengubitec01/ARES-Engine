"""Dual-Level 회수 (R-3, 비그래프 근사) — 저수준(엔티티)+고수준(주제) 키워드 각각 회수 후 병합.

LightRAG 원판은 그래프 엔티티/관계 KV 인덱스 필요 → 비그래프 쿼리시점 근사:
  LLM이 질문에서 low(구체 엔티티·고유명사)·high(주제·개념) 키워드 추출 →
  원 질문 회수 ∪ low 키워드 회수 ∪ high 키워드 회수.
예상: 회수 확장축(R-2·A-7 동류)이라 노이즈로 net 부정~중립.
"""
import json
import re
from typing import Dict, List

from pipeline.shared.embedding import cosine, embed_query_dense
from pipeline.shared.llm import chat
from .base import register

DUAL_PROMPT = """질문에서 두 종류 키워드를 뽑아라.
- low: 구체적 엔티티·고유명사(인물·기관·제품명 등)
- high: 주제·개념·범주 수준 키워드
[출력] 오직 JSON: {"low": [...], "high": [...]}"""


def _dense_topk(emb, chunk_emb, k):
    return [ci for _, ci in sorted(((cosine(emb, e), ci) for ci, e in chunk_emb.items()),
                                   reverse=True)[:k]]


def _parse(content):
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if m:
        try:
            o = json.loads(m.group())
            low = [str(x).strip() for x in o.get("low", []) if str(x).strip()]
            high = [str(x).strip() for x in o.get("high", []) if str(x).strip()]
            return low, high
        except Exception:
            pass
    return [], []


@register("dual_level")
def retrieve(query_emb: List[float], top_k: int, *,
             chunk_emb: Dict[int, List[float]], query_text: str, low_high_k: int = 8) -> List[int]:
    content, _ = chat(DUAL_PROMPT, f"[질문]\n{query_text}", max_tokens=120)
    low, high = _parse(content)
    pool = _dense_topk(query_emb, chunk_emb, top_k)
    seen = set(pool)
    for kws in (low, high):
        if kws:
            emb = embed_query_dense(" ".join(kws))
            for ci in _dense_topk(emb, chunk_emb, low_high_k):
                if ci not in seen:
                    seen.add(ci); pool.append(ci)
    return pool
