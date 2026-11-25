"""pipeline synthesizer — stage 리스트를 순차 실행하는 조합형 합성기.

YAML 사용 예:
  synthesizer:
    type: pipeline
    stages:
      - {type: relevance_filter, prompt: relevance_strict}
      - {type: claim_extraction, prompt: claim_strict}
      - {type: reduce, prompt: system_baseline}

기법 토글 = stages 리스트 편집. 기존 모놀리식 합성기는 그대로 유지(backward compat).

stage 모듈은 import 시 자기 등록되므로, 이 모듈에서 일괄 import.
"""
from typing import Dict, List

from pipeline.shared.llm import usage_sum
from .base import register

# stage 모듈 import → STAGES registry 채움
from .stages import single_shot, relevance_filter, claim_extraction, reduce, verify, entity_group, critic_gated, rerank, answer_type_filter, relation_inject, community_inject, route_inject  # noqa: F401
from .stages.base import STAGES


@register("pipeline")
def synthesize(question: str,
               candidates: List[int],
               chunks_db: Dict[int, Dict],
               *,
               stages: List[Dict]) -> Dict:
    """stages를 순차 실행하며 ctx를 진화시킴.

    stages: YAML에서 온 stage spec list. 각 항목 = {type, ...(stage state)}.
    runner가 미리 prompt 이름들을 PROMPT 상수로 resolve해서 넘긴다.
    """
    ctx = {"candidates": candidates, "usages": [], "calls": 0}

    for s in stages:
        stype = s["type"]
        if stype not in STAGES:
            raise ValueError(f"알 수 없는 stage type: {stype}. 등록된 stages={list(STAGES)}")
        state = {k: v for k, v in s.items() if k != "type"}
        ctx = STAGES[stype](question, ctx, chunks_db, **state)

    return {
        "answer": ctx.get("answer", ""),
        "retrieved_chunks": candidates,
        "relevant_chunks": ctx.get("relevant_chunks"),
        "claims": ctx.get("claims"),
        "draft": ctx.get("draft"),
        "usage": usage_sum(*ctx["usages"]),
        "llm_calls": ctx["calls"],
        "stages_run": [s["type"] for s in stages],
        "qtype": ctx.get("qtype"),
    }
