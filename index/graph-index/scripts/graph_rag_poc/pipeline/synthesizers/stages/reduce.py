"""reduce stage — 추출된 claims를 종합해 최종 답변 생성.

input ctx: claims (있으면 claims 기반, 없으면 candidates를 직접 컨텍스트로)
output ctx: answer
"""
from pipeline.shared.llm import chat
from pipeline.synthesizers.base import build_plain_context
from .base import register


@register("reduce")
def stage(question, ctx, chunks_db, *, prompt, max_tokens=800, max_chars_per_chunk=700):
    if "claims" in ctx and ctx["claims"]:
        user_msg = f"[추출된 사실]\n{ctx['claims']}\n\n[질문]\n{question}"
    else:
        context = build_plain_context(ctx["candidates"], chunks_db, max_chars_per_chunk)
        user_msg = f"{context}\n\n[질문]\n{question}"
    answer, usage = chat(prompt, user_msg, max_tokens=max_tokens)
    ctx["answer"] = answer
    ctx["usages"].append(usage)
    ctx["calls"] += 1
    return ctx
