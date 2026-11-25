"""Sub-Question Decomposition 합성기 (A-2) — 질문을 sub-Q로 분해 → 각 sub-Q별 claim 추출 → 종합.

baseline lazy_qt(relevance → claim → reduce)와의 유일한 차이:
  claim 추출을 'sub-Q별로 분할' 수행 → 각 측면을 독립적으로 빠짐없이 추출 → 한 번에 reduce.
relevance·reduce 프롬프트는 baseline과 동일 → A-2(분해)의 순효과만 격리.

설계 의도:
- 분산통합(인물·기관 경력 종합)에서 측면별 누락 방지 = Full '디스크립션 pre-aggregate' 효과 모사.
- 관계/단순 질문은 decompose 프롬프트가 분해 안 함(sub_questions=[원질문]) → baseline과 동일 행동
  → egroup이 망쳤던 환각 trap 영역을 구조적으로 회피(엔티티 인접배치 없음).

콜 = 1(relevance) + 1(decompose) + N(sub-Q claim) + 1(reduce). N은 MAX_SUBQ로 캡.
"""
import json
import re
from typing import Dict, List

from pipeline.shared.llm import chat, usage_sum
from .base import numbered_chunks, register
from .prompts.relevance_strict import PROMPT as RELEVANCE_DEFAULT
from .prompts.claim_strict import PROMPT as CLAIM_DEFAULT
from .prompts.system_baseline import PROMPT as REDUCE_DEFAULT
from .prompts.subq_decompose import PROMPT as DECOMPOSE_DEFAULT

MAX_SUBQ = 4


def _parse_relevant(content: str, candidates: List[int]) -> List[int]:
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


def _parse_subqs(content: str, question: str) -> List[str]:
    """{"sub_questions": [...]} 파싱. 실패/빈값/1개면 [원질문](= baseline 행동)."""
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group()).get("sub_questions", [])
            subs = [str(x).strip() for x in arr if str(x).strip()]
            if len(subs) >= 2:
                return subs[:MAX_SUBQ]
        except Exception:
            pass
    return [question]


@register("subq_decompose")
def synthesize(question: str,
               candidates: List[int],
               chunks_db: Dict[int, Dict],
               *,
               relevance_prompt: str = RELEVANCE_DEFAULT,
               decompose_prompt: str = DECOMPOSE_DEFAULT,
               claim_prompt: str = CLAIM_DEFAULT,
               reduce_prompt: str = REDUCE_DEFAULT,
               max_chars_per_chunk: int = 600) -> Dict:
    usages = []

    # 1. relevance 필터 (원 질문 기준, baseline과 동일)
    rel_content, u = chat(
        relevance_prompt,
        f"[질문]\n{question}\n\n[청크]\n{numbered_chunks(candidates, chunks_db, max_chars_per_chunk)}",
        max_tokens=200,
    )
    usages.append(u)
    relevant = [ci for ci in _parse_relevant(rel_content, candidates) if ci in chunks_db]
    if not relevant:
        relevant = candidates

    # 2. 분해
    dec_content, u = chat(decompose_prompt, f"[질문]\n{question}", max_tokens=200)
    usages.append(u)
    sub_qs = _parse_subqs(dec_content, question)

    # 3. sub-Q별 claim 추출 (같은 relevant 풀에서)
    ctx_chunks = numbered_chunks(relevant, chunks_db, max_chars_per_chunk)
    claim_blocks = []
    for sq in sub_qs:
        claims, u = chat(
            claim_prompt,
            f"[질문]\n{sq}\n\n[청크]\n{ctx_chunks}",
            max_tokens=900,
        )
        usages.append(u)
        claim_blocks.append(f"## {sq}\n{claims}" if len(sub_qs) > 1 else claims)
    merged_claims = "\n\n".join(claim_blocks)

    # 4. 종합 (원 질문 기준, baseline과 동일 reduce 프롬프트)
    answer, u = chat(
        reduce_prompt,
        f"[추출된 사실]\n{merged_claims}\n\n[질문]\n{question}",
        max_tokens=800,
    )
    usages.append(u)

    return {
        "answer": answer,
        "retrieved_chunks": candidates,
        "relevant_chunks": sorted(set(relevant)),
        "claims": merged_claims,
        "sub_questions": sub_qs,
        "usage": usage_sum(*usages),
        "llm_calls": 3 + len(sub_qs),
    }
