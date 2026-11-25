"""single_shot stage — 후보 청크를 한 번에 LLM에 넣어 답변.

input ctx: candidates
output ctx: answer
"""
from pipeline.shared.llm import chat
from pipeline.synthesizers.base import build_plain_context
from .base import register


@register("single_shot")
def stage(question, ctx, chunks_db, *, prompt, max_tokens=800, max_chars_per_chunk=700):
    context = build_plain_context(ctx["candidates"], chunks_db, max_chars_per_chunk)
    answer, usage = chat(prompt, f"{context}\n\n[질문]\n{question}", max_tokens=max_tokens)
    ctx["answer"] = answer
    ctx["usages"].append(usage)
    ctx["calls"] += 1
    return ctx
