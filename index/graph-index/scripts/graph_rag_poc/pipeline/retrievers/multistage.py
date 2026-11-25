"""Multi-Stage 회수 (R-6, 비그래프판) — 순차 coarse-to-fine.

stage1: dense(BGE) 광범위 회수(recall 우선, stage1_k개)
stage2: 그 결과를 BM25 lexical 점수로 재정렬(precision) → 상위 top_k

R-2(dense+sparse 병렬 융합)와 차이 = 순차(dense 필터 후 sparse 재정렬).
R-6의 그래프판("LLM path 생성→KG 추출")은 Full 그래프 필요라 제외, 비그래프 순차판만 측정.
"""
from typing import Dict, List

from pipeline.shared.embedding import cosine
from .base import register
from .hybrid import BM25  # noqa: F401  (타입 참고용; 실제 인스턴스는 runner가 주입)


@register("multistage")
def retrieve(query_emb: List[float], top_k: int, *,
             chunk_emb: Dict[int, List[float]], bm25, query_text: str,
             stage1_k: int = 30) -> List[int]:
    # stage1: dense 광범위
    s1 = [ci for _, ci in sorted(((cosine(query_emb, e), ci) for ci, e in chunk_emb.items()),
                                 reverse=True)[:stage1_k]]
    # stage2: BM25 lexical 재정렬
    sc = bm25.scores(query_text)
    ranked = sorted(s1, key=lambda c: sc.get(c, 0.0), reverse=True)
    return ranked[:top_k]
