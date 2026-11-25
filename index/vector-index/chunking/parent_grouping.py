"""Parent-document grouping (emb_adj).

인접 청크 임베딩의 코사인 유사도가 낮은 지점에서만 끊어, 연속(=의미가 이어지는)
청크들을 하나의 parent로 묶는다. 검색은 작은 child로(정밀), 반환은 parent째로(문맥).

설계 근거: 메모리 parent_chunking_decision_2026-06-12.
  - LLM 의미분할은 실제 한글문서서 과분할로 폐기. emb_adj가 전 포맷 일관 + 연속보존 + 비용 0.
  - 임베딩은 이미 검색용으로 계산되므로 추가 비용 없음(코사인 계산만).

파라미터(검증된 디폴트):
  PERCENTILE=20  인접 유사도 하위 이 percentile 미만에서만 끊음(낮을수록 coarse)
  MIN_CHARS=1500 parent 최소 크기(이만큼 차기 전엔 안 끊음)
  MAX_CHARS=5000 parent 최대 크기(넘으면 강제로 끊음)
"""
from __future__ import annotations

import math
import os
import statistics
from typing import List, Sequence

PARENT_VERSION = int(os.getenv("PARENT_VERSION", "1"))
PERCENTILE = int(os.getenv("PARENT_PERCENTILE", "20"))
MIN_CHARS = int(os.getenv("PARENT_MIN_CHARS", "1500"))
MAX_CHARS = int(os.getenv("PARENT_MAX_CHARS", "5000"))


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    return dot / (math.sqrt(na) * math.sqrt(nb) + 1e-9)


def assign_parent_ids(
    vectors: List[Sequence[float]],
    char_lengths: List[int],
    percentile: int = PERCENTILE,
    min_chars: int = MIN_CHARS,
    max_chars: int = MAX_CHARS,
) -> List[int]:
    """청크 dense 벡터 + 글자수(청크순서) → 각 청크의 parent_id(0,1,2...).

    vectors[i] 와 char_lengths[i] 는 같은 청크(chunk_index 오름차순)에 대응해야 한다.
    """
    n = len(vectors)
    if n == 0:
        return []
    if n == 1:
        return [0]
    if len(char_lengths) != n:
        # 방어: 길이 불일치 시 전부 한 parent (안전한 over-merge)
        return [0] * n

    sims = [_cosine(vectors[i], vectors[i + 1]) for i in range(n - 1)]
    if len(sims) > 10:
        thr = statistics.quantiles(sims, n=100)[percentile - 1]
    else:
        thr = min(sims)

    parents = [0] * n
    pid = 0
    acc = char_lengths[0]
    for i in range(n - 1):
        nlen = char_lengths[i + 1]
        brk = (sims[i] < thr and acc >= min_chars) or (acc + nlen > max_chars)
        if brk:
            pid += 1
            acc = nlen
        else:
            acc += nlen
        parents[i + 1] = pid
    return parents
