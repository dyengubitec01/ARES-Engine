"""critic_gated stage — A-1 Query Routing + A-3 critic 결합.

핵심 교훈 대응: critic(관계 날조 교정)은 '두 대상의 직접 관계 유무' 트랩에만 도움이고,
집계·나열·역할오귀속 질문엔 부작용(Q15 0.8→0.7, 실도메인 Q14 0.4→0.0).
→ 별도 분류 호출(LLM)로 'relation-pair 질문'인지 판정해, 맞을 때만 critic 교정 적용.
   아니면 draft 그대로(no-op). critic_v2의 프롬프트 자가게이팅 실패를 명시 분류로 해결.

input ctx: answer(draft), candidates
output ctx: answer(관계트랩이면 교정본, 아니면 draft 유지), qtype
LLM 1콜(분류) + 관계트랩일 때만 1콜(교정).
"""
import json
import re

from pipeline.shared.llm import chat
from pipeline.synthesizers.base import build_plain_context
from .base import register

CLASSIFY_PROMPT = """질문이 '특정 두(이상) 대상 사이에 직접적인 관계가 있는지'를 핵심으로 묻는지 판정하라.
- true: "A와 B는 어떤 관계인가", "A와 B는 무슨 사이인가"처럼 두 특정 대상의 직접 관계 유무가 핵심인 질문.
- false: 한 대상의 경력·역할·연결 인물 나열, 정보 집계, 분류, 단순 사실, 절차/단계 등 그 외 전부.
[출력] 오직 JSON: {"relation_pair_question": true 또는 false}"""


def _is_relation_pair(content):
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if m:
        try:
            return bool(json.loads(m.group()).get("relation_pair_question"))
        except Exception:
            pass
    return "true" in content.lower()


@register("critic_gated")
def stage(question, ctx, chunks_db, *, prompt, max_tokens=800, max_chars_per_chunk=700, use_relevant=False):
    # 1) 분류
    cls, u = chat(CLASSIFY_PROMPT, f"[질문]\n{question}", max_tokens=20)
    ctx["usages"].append(u)
    ctx["calls"] += 1
    is_trap = _is_relation_pair(cls)
    ctx["qtype"] = "relation_pair" if is_trap else "other"

    if not is_trap:
        return ctx  # 관계트랩 아니면 critic 미적용 (draft 유지)

    # 2) 관계트랩일 때만 critic 교정
    draft = ctx.get("answer", "")
    # use_relevant: relevance_filter가 정제한 청크만 critic에 (노이즈 풀 대신) → 관계 근거 판단 정확도↑, 과교정↓
    src = ctx.get("relevant_chunks") or ctx["candidates"] if use_relevant else ctx["candidates"]
    context = build_plain_context(src, chunks_db, max_chars_per_chunk)
    final, u2 = chat(
        prompt,
        f"[컨텍스트]\n{context}\n\n[질문]\n{question}\n\n[초안 답변]\n{draft}",
        max_tokens=max_tokens,
    )
    ctx["draft"] = draft
    ctx["answer"] = final
    ctx["usages"].append(u2)
    ctx["calls"] += 1
    return ctx
