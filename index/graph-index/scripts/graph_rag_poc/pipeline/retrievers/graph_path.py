"""Topology/Path Discovery 회수 (R-4) — 질문 엔티티쌍 사이 최단경로 위 엔티티의 청크 회수.

R-8(k-hop 확장)과 달리, 시드 엔티티들 '사이를 잇는 경로'에 초점(관계 추론용 구조 회수).
기존 GLiNER2 공출현 그래프 사용(Full 추출 불요). 예상: 그래프-회수 축(R-8·exp04 중립)이라 중립.

알고리즘: 질문→top_entities 시드 → 모든 시드쌍 BFS 최단경로(≤max_path_len) → 경로 노드 합집합 →
경로 없으면 1-hop 폴백 → 노드 등장 청크 → 질문 cosine 정렬 → top_k.
"""
import collections
from typing import Dict, List, Set

from pipeline.shared.embedding import cosine
from .base import register


@register("graph_path")
def retrieve(query_emb: List[float], top_k: int, *,
             chunk_emb: Dict[int, List[float]], graph: Dict, entity_emb: Dict[str, List[float]],
             top_entities: int = 6, max_path_len: int = 3) -> List[int]:
    ent_scores = sorted(((cosine(query_emb, e), n) for n, e in entity_emb.items()), reverse=True)
    seeds = [n for _, n in ent_scores[:top_entities]]

    edges = graph.get("relation_edges") or graph.get("edges", [])
    adj: Dict[str, Set[str]] = {}
    for rel in edges:
        s, t = rel.get("source"), rel.get("target")
        if s and t:
            adj.setdefault(s, set()).add(t)
            adj.setdefault(t, set()).add(s)

    def bfs_path(src, dst, maxlen):
        if src == dst:
            return [src]
        q = collections.deque([[src]]); seen = {src}
        while q:
            p = q.popleft()
            if len(p) > maxlen:
                continue
            for nb in adj.get(p[-1], ()):
                if nb == dst:
                    return p + [nb]
                if nb not in seen:
                    seen.add(nb); q.append(p + [nb])
        return None

    nodes: Set[str] = set(seeds)
    for i in range(len(seeds)):
        for j in range(i + 1, len(seeds)):
            path = bfs_path(seeds[i], seeds[j], max_path_len)
            if path:
                nodes.update(path)
    if len(nodes) <= len(seeds):  # 경로 못 찾으면 1-hop 폴백
        for s in seeds:
            nodes |= adj.get(s, set())

    entity_chunks = graph.get("entity_chunks", {})
    cand: Set[int] = set()
    for n in nodes:
        cand.update(entity_chunks.get(n, []))
    scored = sorted(((cosine(query_emb, chunk_emb[ci]), ci) for ci in cand if ci in chunk_emb), reverse=True)
    return [ci for _, ci in scored[:top_k]]
