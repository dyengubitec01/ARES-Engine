"""entity_group stage — claim 추출 전, relevant 청크를 질문 타깃 엔티티별로 묶어 재정렬.

기법: I-3 (Entity/Relation KV Store)의 쿼리시점 구현. 그래프 인덱스 없이,
질문에서 뽑은 엔티티 이름으로 후보 청크를 그룹핑해 claim 추출 입력 순서를 재배치.

가설 (Tier-1 분산통합 Q5·6·8): 한 인물·기관에 흩어진 근거를 인접 배치하면
claim 추출이 조각내지 않고 통합 → Full의 '엔티티 디스크립션 pre-aggregate' 효과를
쿼리시점에 모사.

input ctx:  relevant_chunks (없으면 candidates)
output ctx: relevant_chunks (엔티티별 그룹 순서로 재정렬),
            entity_groups (디버그용 {엔티티명: [chunk...]})
LLM 1콜(질문 타깃 엔티티 추출). 엔티티 0개 또는 매칭 0이면 순서 유지(no-op, 안전).
"""
import json
import re

from pipeline.shared.llm import chat
from .base import register


def _parse_entities(content):
    """{"entities": [...]} 파싱. 실패 시 빈 리스트(→ no-op)."""
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group()).get("entities", [])
            return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
    return []


@register("entity_group")
def stage(question, ctx, chunks_db, *, prompt, max_tokens=120):
    source = ctx.get("relevant_chunks") or ctx["candidates"]

    ent_content, usage = chat(prompt, f"[질문]\n{question}", max_tokens=max_tokens)
    ctx["usages"].append(usage)
    ctx["calls"] += 1
    entities = _parse_entities(ent_content)

    if not entities:
        return ctx  # 엔티티 못 뽑으면 순서 유지

    # 각 엔티티명이 본문에 등장하는 청크를 그룹핑 (substring 매칭). 한 청크는 첫 매칭 엔티티에만.
    seen, ordered, groups = set(), [], {}
    for ent in entities:
        grp = [ci for ci in source
               if ci not in seen and ent in (chunks_db.get(ci, {}).get("text") or "")]
        if grp:
            groups[ent] = grp
            seen.update(grp)
            ordered.extend(grp)
    # 어느 엔티티에도 안 걸린 나머지는 원래 순서로 뒤에 보존
    ordered.extend(ci for ci in source if ci not in seen)

    ctx["relevant_chunks"] = ordered
    ctx["entity_groups"] = groups
    return ctx
