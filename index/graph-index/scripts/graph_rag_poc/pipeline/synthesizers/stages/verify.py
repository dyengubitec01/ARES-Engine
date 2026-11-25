"""verify stage — 이전 stage의 answer를 draft로 취급, 컨텍스트 기반 교정.

input ctx: answer (이전 stage가 만든 draft), candidates
output ctx: answer (교정본). draft는 ctx['draft']에 보존.
"""
from pipeline.shared.llm import chat
from pipeline.synthesizers.base import build_plain_context
from .base import register


@register("verify")
def stage(question, ctx, chunks_db, *, prompt, max_tokens=800, max_chars_per_chunk=700):
    draft = ctx.get("answer", "")
    context = build_plain_context(ctx["candidates"], chunks_db, max_chars_per_chunk)
    final, usage = chat(
        prompt,
        f"[컨텍스트]\n{context}\n\n[질문]\n{question}\n\n[초안 답변]\n{draft}",
        max_tokens=max_tokens,
    )
    ctx["draft"] = draft
    ctx["answer"] = final
    ctx["usages"].append(usage)
    ctx["calls"] += 1
    return ctx
