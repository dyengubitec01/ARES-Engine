"""Hybrid 회수 (R-2) — dense(BGE cosine) + sparse(BM25) 가중 결합.

기법 R-2 (LightRAG/K²RAG). dense가 놓치는 '정확한 표면형(엔티티명·고유명사) 언급 청크'를
BM25 lexical로 보강 → 분산통합·fanout의 회수 누락 완화 가설.

회수 풀 자체를 바꾸는 첫 기법 (egroup·A-2는 같은 vector top-20 풀 재조직에 그침).

의존성 없이 BM25 직접 구현. 한국어는 konlpy 없이 [한글 bigram + 영숫자 토큰]으로 근사.
결합: score = alpha*dense_norm + (1-alpha)*bm25_norm  (각 min-max 정규화, 기본 alpha=0.7 dense-leaning).
"""
import math
import re
from collections import Counter
from typing import Dict, List

from pipeline.shared.embedding import cosine
from .base import register

_TOKEN = re.compile(r"[a-zA-Z0-9]+")
_HANGUL = re.compile(r"[가-힣]+")


def tokenize(text: str) -> List[str]:
    """영숫자 토큰(소문자) + 한글 음절 bigram. konlpy 없이 한국어 lexical 근사."""
    text = (text or "").lower()
    toks = _TOKEN.findall(text)
    for run in _HANGUL.findall(text):
        if len(run) == 1:
            toks.append(run)
        else:
            toks.extend(run[i:i + 2] for i in range(len(run) - 1))  # 음절 bigram
    return toks


class BM25:
    """표준 BM25 (k1=1.5, b=0.75). 코퍼스 1회 인덱싱 후 쿼리별 점수."""

    def __init__(self, chunks: List[Dict], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.ids = [c["chunk_index"] for c in chunks]
        self.docs = {c["chunk_index"]: tokenize(c.get("text", "")) for c in chunks}
        self.dl = {ci: len(toks) for ci, toks in self.docs.items()}
        self.avgdl = (sum(self.dl.values()) / len(self.dl)) if self.dl else 0.0
        self.tf = {ci: Counter(toks) for ci, toks in self.docs.items()}
        df = Counter()
        for toks in self.docs.values():
            df.update(set(toks))
        N = len(self.docs)
        self.idf = {t: math.log(1 + (N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def scores(self, query: str) -> Dict[int, float]:
        q = [t for t in set(tokenize(query)) if t in self.idf]
        out = {}
        for ci in self.ids:
            tf, dl, s = self.tf[ci], self.dl[ci], 0.0
            for t in q:
                f = tf.get(t, 0)
                if f:
                    s += self.idf[t] * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl + 1e-9)))
            out[ci] = s
        return out


def _minmax(d: Dict[int, float]) -> Dict[int, float]:
    if not d:
        return {}
    lo, hi = min(d.values()), max(d.values())
    if hi - lo < 1e-12:
        return {k: 0.0 for k in d}
    return {k: (v - lo) / (hi - lo) for k, v in d.items()}


@register("hybrid")
def retrieve(query_emb: List[float], top_k: int, *,
             chunk_emb: Dict[int, List[float]], bm25: BM25, query_text: str,
             alpha: float = 0.7) -> List[int]:
    """dense cosine + BM25 → min-max 정규화 후 alpha 가중합 → top_k."""
    dense = {ci: cosine(query_emb, e) for ci, e in chunk_emb.items()}
    sparse = bm25.scores(query_text)
    dn, sn = _minmax(dense), _minmax(sparse)
    combined = {ci: alpha * dn.get(ci, 0.0) + (1 - alpha) * sn.get(ci, 0.0) for ci in chunk_emb}
    return [ci for ci, _ in sorted(combined.items(), key=lambda kv: kv[1], reverse=True)[:top_k]]
