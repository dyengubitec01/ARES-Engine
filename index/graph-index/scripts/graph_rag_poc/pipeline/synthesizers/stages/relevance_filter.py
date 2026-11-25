"""relevance_filter stage — LLM이 후보 청크 중 직접 답 되는 것만 선별.

input ctx: candidates
output ctx: relevant_chunks (필터 통과한 청크들)
"""
import json
import re

from pipeline.shared.llm import chat
from pipeline.synthesizers.base import numbered_chunks
from .base import register


def _parse_relevant(content, candidates):
    """파싱 실패 시 안전한 폴백(상위 8개)."""
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


@register("relevance_filter")
def stage(question, ctx, chunks_db, *, prompt, max_tokens=200, max_chars_per_chunk=600):
    candidates = ctx["candidates"]
    rel_content, usage = chat(
        prompt,
        f"[질문]\n{question}\n\n[청크]\n{numbered_chunks(candidates, chunks_db, max_chars_per_chunk)}",
        max_tokens=max_tokens,
    )
    relevant = [ci for ci in _parse_relevant(rel_content, candidates) if ci in chunks_db]
    if not relevant:
        relevant = candidates
    ctx["relevant_chunks"] = sorted(set(relevant))
    ctx["usages"].append(usage)
    ctx["calls"] += 1
    return ctx
