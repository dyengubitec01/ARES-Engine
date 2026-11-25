"""Draft + verify 2단계 합성 — single_shot 후 컨텍스트 기반 교정.

이전: scripts/graph_rag_poc/_shared/lazy_value_test/eval_abstain.py: call_verify

성능 (1000청크 환각 15문): judge 0.567. strict_b1(1콜) 0.747 / lazy_qt(3콜) 0.827.
strict_b1보다 못해서 양산 후보 아님. 참고용/벤치마크용 보존.
"""
from typing import Dict, List

from pipeline.shared.llm import chat, usage_sum
from .base import build_plain_context, register
from .prompts.system_baseline import PROMPT as BASELINE_DEFAULT
from .prompts.verify_v1 import PROMPT as VERIFY_DEFAULT


@register("verify")
def synthesize(question: str,
               candidates: List[int],
               chunks_db: Dict[int, Dict],
               *,
               draft_prompt: str = BASELINE_DEFAULT,
               verify_prompt: str = VERIFY_DEFAULT,
               max_chars_per_chunk: int = 700) -> Dict:
    """1) baseline으로 draft → 2) verify로 컨텍스트 기반 교정."""
    context = build_plain_context(candidates, chunks_db, max_chars_per_chunk)

    # 1. draft
    draft, u1 = chat(draft_prompt, f"{context}\n\n[질문]\n{question}", max_tokens=800)

    # 2. verify
    final, u2 = chat(
        verify_prompt,
        f"[컨텍스트]\n{context}\n\n[질문]\n{question}\n\n[초안 답변]\n{draft}",
        max_tokens=800,
    )

    return {
        "answer": final,
        "retrieved_chunks": candidates,
        "draft": draft,
        "usage": usage_sum(u1, u2),
        "llm_calls": 2,
    }
