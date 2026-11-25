"""answer_type_filter stage — R-9 Answer Type Prediction.

답 유형(인물/기관/날짜/목록/관계/설명 등)을 예측한 뒤, 그 유형 정보를 담은 청크만 선별.
relevance_filter(유형 무관 선별)의 '유형 인지' 변형. 격리: 이 stage로 relevance_filter를 대체.
콜 2 = 유형예측 + 유형인지 필터.

input ctx: candidates
output ctx: relevant_chunks, answer_type
"""
import json
import re

from pipeline.shared.llm import chat
from pipeline.synthesizers.base import numbered_chunks
from .base import register

TYPE_PROMPT = """질문에 대한 답이 어떤 '유형'인지 한 단어로 예측하라.
예: 인물, 기관, 날짜, 수치, 목록(나열), 관계, 분류, 설명/사유.
[출력] 유형 단어만 (설명 없이)."""


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
    nums = [int(n) for n in re.findall(r"chunk\s*(\d+)", content)]
    return nums or candidates[:8]


@register("answer_type_filter")
def stage(question, ctx, chunks_db, *, prompt, max_tokens=200, max_chars_per_chunk=600):
    cands = ctx["candidates"]
    atype, u1 = chat(TYPE_PROMPT, f"[질문]\n{question}", max_tokens=20)
    ctx["usages"].append(u1); ctx["calls"] += 1
    atype = atype.strip()[:30]
    content, u2 = chat(
        prompt,
        f"[질문]\n{question}\n\n[예상 답 유형] {atype}\n\n[청크]\n{numbered_chunks(cands, chunks_db, max_chars_per_chunk)}",
        max_tokens=max_tokens,
    )
    ctx["usages"].append(u2); ctx["calls"] += 1
    relevant = [c for c in _parse_relevant(content, cands) if c in chunks_db] or cands
    ctx["relevant_chunks"] = sorted(set(relevant))
    ctx["answer_type"] = atype
    return ctx
