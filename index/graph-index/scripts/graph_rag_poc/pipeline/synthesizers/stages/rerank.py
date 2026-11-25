"""rerank stage — R-7 LLM listwise 재랭킹. 후보 풀을 관련도순 재정렬 → 상위 top_n 유지.

R-5(multihop)가 넓힌 풀에서 노이즈 청크를 뒤로 밀거나 제외(precision↑).
회수(R-5)와 다른 축. 인프라에 cross-encoder 리랭커 없어 LLM 1콜 listwise로 구현.

input ctx: candidates
output ctx: candidates (관련도순 재정렬 + top_n 트림)
LLM 1콜.
"""
import json
import re

from pipeline.shared.llm import chat
from pipeline.synthesizers.base import numbered_chunks
from .base import register


def _parse_ranked(content, cands):
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group()).get("ranked", [])
            out = [int(x) for x in arr
                   if str(x).lstrip("-").isdigit() and int(x) in cands]
            if out:
                return out
        except Exception:
            pass
    nums = [int(n) for n in re.findall(r"\d+", content) if int(n) in cands]
    return nums or cands


@register("rerank")
def stage(question, ctx, chunks_db, *, prompt, top_n=12, max_tokens=200, max_chars_per_chunk=400):
    cands = ctx["candidates"]
    content, u = chat(
        prompt,
        f"[질문]\n{question}\n\n[청크]\n{numbered_chunks(cands, chunks_db, max_chars_per_chunk)}",
        max_tokens=max_tokens,
    )
    ctx["usages"].append(u)
    ctx["calls"] += 1
    ranked = _parse_ranked(content, cands)
    seen = set(ranked)
    rest = [c for c in cands if c not in seen]  # 누락 후보는 뒤에 보존(안전)
    ctx["candidates"] = (ranked + rest)[:top_n]
    return ctx
