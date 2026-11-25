"""단일 LLM 호출 답변 — prompt만 교체해서 vector / vector_strict / vector_pro 다 커버.

이전:
- evaluate.py: call_gemma_plain (vector baseline)
- eval_abstain.py: call_strict (vector_strict)
- add_vector_pro.py: call_pro (vector_pro)

세 트랙의 차이는 오직 system prompt 선택. 합성기는 하나만 있으면 됨.
"""
from typing import Dict, List

from pipeline.shared.llm import chat
from .base import build_plain_context, register


@register("single_shot")
def synthesize(question: str,
               candidates: List[int],
               chunks_db: Dict[int, Dict],
               *,
               system_prompt: str,
               max_tokens: int = 800,
               max_chars_per_chunk: int = 700) -> Dict:
    """후보 청크들을 통째로 LLM에 넣고 답변 받기.

    system_prompt를 다르게 주면:
    - prompts.system_baseline.PROMPT → vector baseline
    - prompts.strict_b1.PROMPT       → vector_strict (관계 기권 규칙 추가)
    - prompts.pro_v1.PROMPT          → vector_pro (운영급 모범)
    """
    context = build_plain_context(candidates, chunks_db, max_chars_per_chunk)
    user_msg = f"{context}\n\n[질문]\n{question}"
    answer, usage = chat(system_prompt, user_msg, max_tokens=max_tokens)
    return {
        "answer": answer,
        "retrieved_chunks": candidates,
        "usage": usage,
        "llm_calls": 1,
    }
