"""relation_inject stage — 구조 축 보강. real청크서 요약한 관계(relation_summaries)를
질문에 등장한 엔티티에 맞춰 claims에 주입. I-7(청크요약)을 '관계'에 적용.

검색 축(R-5/hybrid)·답변 축(critic)과 직교 → 스택에 얹어 net 보탬 여부 측정.
위치: claim_extraction 뒤, reduce 앞. reduce가 관계요약을 사실로 포함 → critic이 검증.

input ctx: claims (claim_extraction 결과)
output ctx: claims (+ 매칭된 관계요약), relation_injected(개수)
"""
import json

from .base import register

_CACHE = {}
GENERIC = {"Autonova", "회사", "자회사", "본사", "팀", "직원", "대표", "팀장"}


def _load(path):
    if path not in _CACHE:
        _CACHE[path] = json.load(open(path, encoding="utf-8"))
    return _CACHE[path]


@register("relation_inject")
def stage(question, ctx, chunks_db, *, summaries_path, max_inject=6):
    sums = _load(summaries_path)
    scored = []
    for o in sums:
        matched = [e for e in o["entities"] if len(e) >= 2 and e not in GENERIC and e in question]
        if matched:
            scored.append((len(matched), o["summary"]))
    scored.sort(key=lambda x: -x[0])  # 두 엔티티 다 등장(관계질문) 우선
    inject = [s for _, s in scored[:max_inject]]
    if inject:
        block = "\n".join(f"- {s} [관계DB]" for s in inject)
        ctx["claims"] = (ctx.get("claims") or "") + "\n" + block
    ctx["relation_injected"] = len(inject)
    return ctx
