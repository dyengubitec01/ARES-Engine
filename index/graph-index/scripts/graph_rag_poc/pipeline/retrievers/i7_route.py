"""I-7 라우팅 회수 — 엔티티/커뮤니티 '설명' pseudo-chunk를 검색 신호로 사용.

설계(I7_BUILD_LOG.md): lazy 원본 청크 + 설명 레이어(chunk_index>=200000)를 한 풀에 임베딩.
  1) 원 쿼리 dense top_k (원본+설명 혼합 풀)
  2) 검색된 '설명' 항목 → 그 설명의 route_chunks를 query 유사도로 재정렬해 상위 route_topn개 원본청크를 풀에 추가(union)
  3) include_desc=False(Track A 라우팅 전용): 설명 자체는 답변풀에서 제외(원본청크만 반환) → 답변은 원본에서만 생성
     include_desc=True (Track B 라우팅+생성): 설명 텍스트도 반환 → 답변 컨텍스트에 포함
반환: 원본청크(직접 검색 + 라우팅으로 끌어온 것) [+ 설명청크(B)].  relevance_filter가 이후 좁힘.
"""
from typing import Dict, List

from pipeline.shared.embedding import cosine
from .base import register


@register("i7_route")
def retrieve(query_emb: List[float], top_k: int, *,
             chunk_emb: Dict[int, List[float]], chunks_db: Dict[int, Dict],
             include_desc: bool = False, route_topn: int = 5,
             desc_min_index: int = 200000) -> List[int]:
    # 1) 원본+설명 혼합 풀에서 dense top_k
    scored = sorted(((cosine(query_emb, e), ci) for ci, e in chunk_emb.items()), reverse=True)
    hits = [ci for _, ci in scored[:top_k]]

    pool, seen = [], set()
    desc_hits = []

    def add(ci):
        if ci not in seen and ci in chunk_emb:
            seen.add(ci); pool.append(ci)

    # 2) 직접 검색된 원본청크 먼저, 설명은 따로 모음
    for ci in hits:
        if ci >= desc_min_index:
            desc_hits.append(ci)
        else:
            add(ci)

    # 3) 검색된 설명 → route_chunks를 query 유사도로 재정렬, 상위 route_topn 원본청크 풀에 추가
    for dci in desc_hits:
        rc = chunks_db.get(dci, {}).get("route_chunks", [])
        rc_scored = sorted(((cosine(query_emb, chunk_emb[c]), c) for c in rc if c in chunk_emb),
                           reverse=True)
        for _, c in rc_scored[:route_topn]:
            add(c)

    # 4) Track B면 설명 청크 자체도 답변풀에 포함
    if include_desc:
        for dci in desc_hits:
            if dci not in seen:
                seen.add(dci); pool.append(dci)

    return pool
