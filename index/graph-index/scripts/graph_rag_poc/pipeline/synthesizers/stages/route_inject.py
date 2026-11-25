"""route_inject — A-1 라우팅 + 구조축 통합. 1 LLM콜로 질문유형 분류 후 맞는 구조요약만 주입.
  relation → 관계요약(엔티티매칭) / global → 커뮤니티요약 / other → 주입 없음.
crude 게이팅(relation_inject 엔티티매칭·community_inject 마커)의 누수(fanout·trap collateral) 해결.

위치: claim_extraction 뒤, reduce 앞. 주입된 요약은 reduce가 사실로 포함, critic이 검증.
"""
import json
import re

from pipeline.shared.llm import chat
from .base import register

_C = {}
GENERIC = {"Autonova", "회사", "자회사", "본사", "팀", "직원", "대표", "팀장"}

CLS = """질문 유형을 분류하라.
- relation: 특정 두(이상) 대상 사이의 관계·보고라인·사제·소속·영입 등을 묻는 질문.
- global: 회사 전반의 전략·철학·가치관·구조·정체성·방향을 종합/정리하라는 질문.
- other: 단순 사실·수치·나열·집계 등 그 외 전부.
[출력] 오직 JSON: {"type":"relation|global|other"}"""


def _load(p):
    if p not in _C:
        _C[p] = json.load(open(p, encoding="utf-8"))
    return _C[p]


@register("route_inject")
def stage(question, ctx, chunks_db, *, relation_path, community_path, max_rel=6, max_comm=4):
    cls, u = chat(CLS, f"[질문]\n{question}", max_tokens=20)
    ctx["usages"].append(u)
    ctx["calls"] += 1
    m = re.search(r'"type"\s*:\s*"(\w+)"', cls)
    qt = m.group(1) if m else "other"
    ctx["route_type"] = qt

    inject = []
    if qt == "relation":
        scored = []
        for o in _load(relation_path):
            matched = [e for e in o["entities"] if len(e) >= 2 and e not in GENERIC and e in question]
            if matched:
                scored.append((len(matched), f"- {o['summary']} [관계DB]"))
        scored.sort(key=lambda x: -x[0])
        inject = [s for _, s in scored[:max_rel]]
    elif qt == "global":
        inject = [f"- [커뮤니티요약] {c['summary']}" for c in _load(community_path)[:max_comm] if c.get("summary")]

    if inject:
        ctx["claims"] = (ctx.get("claims") or "") + "\n" + "\n".join(inject)
    return ctx
