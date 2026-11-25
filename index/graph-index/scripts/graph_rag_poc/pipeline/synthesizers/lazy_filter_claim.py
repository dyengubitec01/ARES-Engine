"""LazyGraphRAG 쿼리시점 합성 — relevance 필터 → claim 추출 → map-reduce 종합.

이전: scripts/graph_rag_poc/_shared/lazy_value_test/eval_real_lazy.py: real_lazy_answer

3 LLM 콜:
1. relevance 필터 — 후보 청크 중 직접 답이 되는 것만 선별
2. claim 추출 — 선별된 청크에서 질문에 답하는 사실만 추출
3. 종합 답변 — 추출된 claim을 입력으로 최종 답변 생성

효과 (1000청크 28문 judge): vector 0.846 → lazy_qt 0.904 (+0.058)
        (환각함정 15문: vector 0.480 → lazy_qt 0.827, 날조율 14/15 → 9/15)
"""
import json
import re
from typing import Dict, List

from pipeline.shared.llm import chat, usage_sum
from .base import numbered_chunks, register

# 기본 system prompts (다른 prompt를 인자로 받을 수도 있음)
from .prompts.relevance_strict import PROMPT as RELEVANCE_DEFAULT
from .prompts.claim_strict import PROMPT as CLAIM_DEFAULT
from .prompts.system_baseline import PROMPT as REDUCE_DEFAULT


def _parse_relevant(content: str, candidates: List[int]) -> List[int]:
    """필터 결과 파싱. 실패 시 안전한 폴백(상위 8개)."""
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group()).get("relevant", [])
            out = [int(x) for x in arr
                   if isinstance(x, (int, str)) and str(x).lstrip("-").isdigit()]
            if out:
                return out
        except Exception:
            pass
    nums = [int(n) for n in re.findall(r"chunk\s*(\d+)", content)]
    return nums or candidates[:8]


@register("lazy_filter_claim")
def synthesize(question: str,
               candidates: List[int],
               chunks_db: Dict[int, Dict],
               *,
               relevance_prompt: str = RELEVANCE_DEFAULT,
               claim_prompt: str = CLAIM_DEFAULT,
               reduce_prompt: str = REDUCE_DEFAULT,
               max_chars_per_chunk: int = 600) -> Dict:
    """relevance → claim → reduce 3단계 합성."""
    in_tok = out_tok = 0
    usages = []

    # 1. relevance 필터
    rel_content, u1 = chat(
        relevance_prompt,
        f"[질문]\n{question}\n\n[청크]\n{numbered_chunks(candidates, chunks_db, max_chars_per_chunk)}",
        max_tokens=200,
    )
    usages.append(u1)
    relevant = [ci for ci in _parse_relevant(rel_content, candidates) if ci in chunks_db]
    if not relevant:
        relevant = candidates

    # 2. claim 추출 (관련 청크 일괄)
    claims, u2 = chat(
        claim_prompt,
        f"[질문]\n{question}\n\n[청크]\n{numbered_chunks(relevant, chunks_db, max_chars_per_chunk)}",
        max_tokens=900,
    )
    usages.append(u2)

    # 3. map-reduce 종합
    answer, u3 = chat(
        reduce_prompt,
        f"[추출된 사실]\n{claims}\n\n[질문]\n{question}",
        max_tokens=800,
    )
    usages.append(u3)

    return {
        "answer": answer,
        "retrieved_chunks": candidates,
        "relevant_chunks": sorted(set(relevant)),
        "claims": claims,
        "usage": usage_sum(*usages),
        "llm_calls": 3,
    }
