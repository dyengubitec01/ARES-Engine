"""Sub-Answer Aggregation 합성기 (G-4). 질문 분해 → sub-Q별 '완전 답변' 생성 → 종합.

A-2(subq_decompose, claim 분해 후 1회 reduce)와의 차이:
  G-4는 각 sub-Q에 대해 독립 답변을 만든 뒤(sub-answer), 그 답변들을 모아 최종 종합.
  (A-2 = claim 레벨 분해 / G-4 = answer 레벨 분해+집계)

콜 = 1(relevance) + 1(decompose) + N(sub-answer) + 1(aggregate).
"""
import json
import re
from typing import Dict, List

from pipeline.shared.llm import chat, usage_sum
from .base import numbered_chunks, register
from .prompts.relevance_strict import PROMPT as RELEVANCE_DEFAULT
from .prompts.system_baseline import PROMPT as BASELINE_DEFAULT
from .prompts.subq_decompose import PROMPT as DECOMPOSE_DEFAULT

MAX_SUBQ = 4
AGG_PROMPT = """아래는 한 질문을 하위 질문으로 나눠 각각 답한 결과다. 이들을 종합해 원 질문에 대한 하나의 완전한 답변을 작성하라. 중복은 합치고 근거(chunk 표기)는 유지하라."""


def _parse_relevant(content, candidates):
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group()).get("relevant", [])
            out = [int(x) for x in arr if str(x).lstrip("-").isdigit()]
            if out:
                return out
        except Exception:
            pass
    return candidates[:8]


def _parse_subqs(content, question):
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


@register("sub_answer_agg")
def synthesize(question, candidates, chunks_db, *,
               relevance_prompt=RELEVANCE_DEFAULT, decompose_prompt=DECOMPOSE_DEFAULT,
               answer_prompt=BASELINE_DEFAULT, aggregate_prompt=AGG_PROMPT,
               max_chars_per_chunk=600):
    usages = []
    rel, u = chat(relevance_prompt,
                  f"[질문]\n{question}\n\n[청크]\n{numbered_chunks(candidates, chunks_db, max_chars_per_chunk)}",
                  max_tokens=200)
    usages.append(u)
    relevant = [c for c in _parse_relevant(rel, candidates) if c in chunks_db] or candidates
    ctx_chunks = numbered_chunks(relevant, chunks_db, max_chars_per_chunk)

    dec, u = chat(decompose_prompt, f"[질문]\n{question}", max_tokens=200)
    usages.append(u)
    sub_qs = _parse_subqs(dec, question)

    sub_answers = []
    for sq in sub_qs:
        ans, u = chat(answer_prompt, f"[청크]\n{ctx_chunks}\n\n[질문]\n{sq}", max_tokens=500)
        usages.append(u)
        sub_answers.append(f"## {sq}\n{ans}" if len(sub_qs) > 1 else ans)
    merged = "\n\n".join(sub_answers)

    if len(sub_qs) > 1:
        final, u = chat(aggregate_prompt, f"[하위 답변들]\n{merged}\n\n[원 질문]\n{question}", max_tokens=800)
        usages.append(u)
    else:
        final = merged

    return {"answer": final, "retrieved_chunks": candidates,
            "relevant_chunks": sorted(set(relevant)), "sub_questions": sub_qs,
            "usage": usage_sum(*usages), "llm_calls": len(usages)}
