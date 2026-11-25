"""Multi-hop iterative 회수 (R-5) — 1차 검색 → LLM 추가검색어 생성 → 2차 타깃 재검색 → 풀 확장.

기법 R-5. lazy_qt가 '직접 hop은 맞히나 간접 체인을 못 조립'하는 관계/fanout 갭(Q15·Q16) 타깃.
R-2(broad lexical)와 달리, 1차 결과의 핵심 엔티티의 '추가 연결'만 정밀 재검색 → 노이즈 최소.

흐름:
  1) 1차: 원 쿼리 dense top_k → cand1
  2) LLM 1콜: 원 질문 + 1차 청크 → 더 찾을 연결 대상 검색어(followups, 최대 2)
     (연결/관계 질문이 아니면 빈 배열 → 2차 없음, vector_topk와 동일 행동 = 자기 게이팅)
  3) 2차: 각 followup 임베딩 → dense top hop2_k → cand1에 추가(dedup)
반환: cand1 ∪ hop2 (relevance_filter가 이후 좁힘).

retriever가 chat/embed 호출 = R-5(LM-in-retrieval) 본질. chat은 gen_temperature 따름.
"""
import json
import re
from typing import Dict, List

from pipeline.shared.embedding import cosine, embed_query_dense
from pipeline.shared.llm import chat
from .base import register

HYDE_PROMPT = """다음 질문에 대한 '그럴듯한 가상 답변'을 2~3문장으로 작성하라(A-7 HyDE). 정확하지 않아도 되며, 답변에 등장할 법한 핵심 용어·이름·사실을 풍부히 포함하라(검색 임베딩 시드용)."""

FOLLOWUP_PROMPT = """질문에 완전히 답하려면 1차 검색 결과에 등장한 핵심 인물/항목 중 '추가로 연결·관계를 더 찾아야 할' 대상을 최대 2개 골라 검색어로 만들어라.
- 두 대상의 관계, 또는 한 인물의 직간접 연결/영향력/보고라인을 묻는 질문에서, 1차 결과의 핵심 인물의 '추가 연결'을 찾는 검색어 (예: "정민호가 영입하거나 지도한 인물", "강현우와 연결된 인물", "오태경의 보고 라인").
- 단순 단일 사실 질문이거나 더 찾을 연결이 없으면 빈 배열.
[출력] 오직 JSON: {"followups": ["...", ...]}"""

MAX_FOLLOWUPS = 2


def _dense_topk(query_emb, chunk_emb, k):
    return [ci for _, ci in sorted(((cosine(query_emb, e), ci) for ci, e in chunk_emb.items()),
                                   reverse=True)[:k]]


def _chunk_text(idxs, chunks_db, max_chars=400):
    out = []
    for ci in idxs:
        c = chunks_db.get(ci)
        if c:
            t = (c.get("text") or "").strip()
            out.append(f"[chunk {ci}]\n{t[:max_chars]}")
    return "\n\n".join(out)


def _parse_followups(content):
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group()).get("followups", [])
            return [str(x).strip() for x in arr if str(x).strip()][:MAX_FOLLOWUPS]
        except Exception:
            pass
    return []


@register("multihop")
def retrieve(query_emb: List[float], top_k: int, *,
             chunk_emb: Dict[int, List[float]], query_text: str, chunks_db: Dict[int, Dict],
             hop2_k: int = 5, seed_ctx: int = 8, use_hyde: bool = False) -> List[int]:
    # A-7 HyDE(옵션): 가상답변 생성→임베딩→1차 회수 시드. else 원 질문 임베딩.
    seed_emb = query_emb
    if use_hyde:
        hyde_ans, _ = chat(HYDE_PROMPT, f"[질문]\n{query_text}", max_tokens=200)
        if hyde_ans.strip():
            seed_emb = embed_query_dense(hyde_ans)
    cand1 = _dense_topk(seed_emb, chunk_emb, top_k)

    # 2차 검색어 생성 (LLM 1콜)
    fu_content, _ = chat(
        FOLLOWUP_PROMPT,
        f"[질문]\n{query_text}\n\n[1차 검색 결과]\n{_chunk_text(cand1[:seed_ctx], chunks_db)}",
        max_tokens=150,
    )
    followups = _parse_followups(fu_content)

    pool, seen = list(cand1), set(cand1)
    for fq in followups:
        fq_emb = embed_query_dense(fq)
        for ci in _dense_topk(fq_emb, chunk_emb, hop2_k):
            if ci not in seen:
                seen.add(ci)
                pool.append(ci)
    return pool
