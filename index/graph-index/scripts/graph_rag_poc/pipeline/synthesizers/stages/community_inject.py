"""community_inject stage — real 서브그래프 커뮤니티 요약을 global/sensemaking 질문에 주입.
구조 축의 'global 짝'(relation_inject는 pairwise 짝). MS GraphRAG식 community report.

gated: 종합·정리·철학·전략·구조·이유 등 global 마커가 질문에 있을 때만(개별/나열 질문엔 노이즈라 skip).
위치: claim_extraction 뒤, reduce 앞.
"""
import json

from .base import register

_CACHE = {}
GLOBAL_MARK = ("종합", "정리", "전반", "전체", "철학", "전략", "문화", "가치관",
               "구조", "방향", "정체성", "이유", "근거", "비롯", "반영")


def _load(path):
    if path not in _CACHE:
        _CACHE[path] = json.load(open(path, encoding="utf-8"))
    return _CACHE[path]


@register("community_inject")
def stage(question, ctx, chunks_db, *, summaries_path, max_inject=4):
    if not any(m in question for m in GLOBAL_MARK):
        ctx["community_injected"] = 0
        return ctx  # global 질문 아니면 주입 안 함
    comms = _load(summaries_path)
    inject = [c["summary"] for c in comms[:max_inject] if c.get("summary")]
    if inject:
        block = "\n".join(f"- [커뮤니티요약] {s}" for s in inject)
        ctx["claims"] = (ctx.get("claims") or "") + "\n" + block
    ctx["community_injected"] = len(inject)
    return ctx
