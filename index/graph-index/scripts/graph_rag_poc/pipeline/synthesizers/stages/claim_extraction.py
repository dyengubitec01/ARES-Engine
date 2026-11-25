"""claim_extraction stage — 관련 청크에서 질문에 답이 되는 사실만 추출.

input ctx: relevant_chunks (없으면 candidates 사용)
output ctx: claims (텍스트, "- 사실 [chunk N]" 형식)
"""
from pipeline.shared.llm import chat
from pipeline.synthesizers.base import numbered_chunks
from .base import register


@register("claim_extraction")
def stage(question, ctx, chunks_db, *, prompt, max_tokens=900, max_chars_per_chunk=600):
    source = ctx.get("relevant_chunks") or ctx["candidates"]
    claims, usage = chat(
        prompt,
        f"[질문]\n{question}\n\n[청크]\n{numbered_chunks(source, chunks_db, max_chars_per_chunk)}",
        max_tokens=max_tokens,
    )
    ctx["claims"] = claims
    ctx["usages"].append(usage)
    ctx["calls"] += 1
    return ctx
