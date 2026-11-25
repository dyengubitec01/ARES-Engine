"""표준 graph_rag — 그래프 순회 단일 표준 retriever (논문 기법 0개).

lazy 공출현 그래프(엔티티/관계/커뮤니티, 설명 없음)의 순회 능력을 한 retriever에 통합.
4개 기법을 한 흐름으로 적용 (각 1이름):
  1) entity_linking : 질문 임베딩 ↔ 엔티티 임베딩 cosine → 시드 엔티티
  2) neighborhood   : 시드에서 그래프 k-hop 이웃 확장 (예전 graph_v2 1-hop + graph_khop k-hop 통합)
  3) path           : 시드 엔티티쌍 사이 최단 관계경로 노드 (관계추론용)
  4) community      : 시드가 속한 커뮤니티의 멤버 (광범위 질문용; 구조만 사용, 요약 없음)
수집 엔티티 → 등장 청크 합집합 → 질문 cosine 정렬 → top_k.
이게 향후 논문 기법(5단계) 비교의 '표준 baseline'.
"""
import collections
from typing import Dict, List, Set

from pipeline.shared.embedding import cosine
from .base import register


def _link(query_emb, entity_emb, k) -> List[str]:
    return [n for _, n in sorted(((cosine(query_emb, e), n) for n, e in entity_emb.items()),
                                 reverse=True)[:k]]


_JOSA = ("이며", "으로서", "로서", "이라는", "라는", "에서", "에게", "부터", "까지",
         "의", "은", "는", "이", "가", "을", "를", "와", "과", "도", "로", "만", "들", "에")


def _core(key: str) -> str:
    """엔티티 키에서 핵심 이름 추출 — 첫 토큰 + 조사/연결어미 반복 제거.
    '송지윤 연구원의'→'송지윤', '정민호이며'→'정민호', 'Autonova의 연구원들'→'Autonova'."""
    head = key.split()[0] if key.split() else key
    while len(head) > 2:
        for j in sorted(_JOSA, key=len, reverse=True):
            if head.endswith(j) and len(head) - len(j) >= 2:
                head = head[:-len(j)]
                break
        else:
            break
    return head


def _link_by_name(query_text: str, entity_chunks: Dict[str, list], max_chunks: int = 100) -> List[str]:
    """질문 텍스트에 '이름이 등장하는' 엔티티 매칭 (cosine보다 정확). 변형 자동 병합(모든 변형 키 포함).
    너무 generic한 엔티티(전체 코퍼스급, chunk>max_chunks)는 시드에서 제외."""
    seeds = []
    for key, chunks in entity_chunks.items():
        if len(chunks) > max_chunks:
            continue
        c = _core(key)
        if len(c) >= 2 and c in query_text:
            seeds.append(key)
    return seeds


def _adjacency(edges) -> Dict[str, Set[str]]:
    adj: Dict[str, Set[str]] = {}
    for rel in edges:
        s, t = rel.get("source"), rel.get("target")
        if s is None or t is None:
            continue
        adj.setdefault(s, set()).add(t)
        adj.setdefault(t, set()).add(s)
    return adj


def _neighborhood(seeds, adj, hops) -> Set[str]:
    expanded, frontier = set(seeds), set(seeds)
    for _ in range(hops):
        nxt: Set[str] = set()
        for n in frontier:
            nxt |= adj.get(n, set())
        nxt -= expanded
        if not nxt:
            break
        expanded |= nxt
        frontier = nxt
    return expanded


def _bfs_path(src, dst, adj, max_len) -> Set[str]:
    if src == dst:
        return {src}
    q = collections.deque([(src, [src])])
    seen = {src}
    while q:
        node, path = q.popleft()
        if len(path) > max_len:
            continue
        for nb in adj.get(node, ()):
            if nb == dst:
                return set(path + [nb])
            if nb not in seen:
                seen.add(nb)
                q.append((nb, path + [nb]))
    return set()


def _paths(seeds, adj, max_len) -> Set[str]:
    seeds = list(seeds)
    nodes: Set[str] = set()
    for i in range(len(seeds)):
        for j in range(i + 1, len(seeds)):
            nodes |= _bfs_path(seeds[i], seeds[j], adj, max_len)
    return nodes


def _community(seeds, graph) -> Set[str]:
    e2members: Dict[str, List[str]] = {}
    for c in graph.get("communities", []):
        members = c.get("members", [])
        for m in members:
            e2members[m] = members
    out: Set[str] = set()
    for s in seeds:
        out.update(e2members.get(s, []))
    return out


@register("graph_rag")
def retrieve(query_emb: List[float], top_k: int, *,
             chunk_emb: Dict[int, List[float]], graph: Dict, entity_emb: Dict[str, List[float]],
             query_text: str = None, top_entities: int = 6, hops: int = 1, max_path_len: int = 3,
             use_community: bool = False, min_rel: int = 1) -> List[int]:
    """그래프 순회로 '질문의 특정 엔티티가 든 관계 청크'를 정밀 회수.

    랭킹 신호(우선순위):
      1) hits = 청크에 든 '질문 관련 엔티티'의 가중합 (seed 3 / path 2 / neighbor 1 / community 0.3)
         → 질문의 시드가 여럿 든 '관계 청크'가 최상위 (vector가 놓친 관계를 보충).
      2) focus = (관련 엔티티 수) / (청크의 전체 엔티티 수)
         → '두 엔티티만 든 관계 청크'(focus↑) > '12명 든 일반 목록 청크'(focus↓).
            일반 목록청크가 모든 질문에 끌려오던 문제 차단. 시드 1개뿐인 distractor도 후순위.
      3) cosine (동점 보조).
    community는 광범위 노이즈원이라 기본 off (use_community=True 시 약하게만).
    """
    entity_chunks = graph.get("entity_chunks", {})
    edges = graph.get("relation_edges") or graph.get("edges", [])
    adj = _adjacency(edges)

    # 1) entity_linking: 질문에 이름이 등장하는 엔티티 매칭(정확·변형병합). 실패 시 cosine 폴백.
    seeds = _link_by_name(query_text, entity_chunks) if query_text else []
    if not seeds:
        seeds = _link(query_emb, entity_emb, top_entities)
    nbr = _neighborhood(seeds, adj, hops) - set(seeds)           # 2) neighborhood(1-hop)
    pth = _paths(seeds, adj, max_path_len) - set(seeds)           # 3) path
    com = (_community(seeds, graph) - set(seeds)) if use_community else set()  # 4) community(기본 off)

    weight: Dict[str, float] = {}
    for e in com:   weight[e] = 0.3
    for e in nbr:   weight[e] = max(weight.get(e, 0.0), 1.0)
    for e in pth:   weight[e] = max(weight.get(e, 0.0), 2.0)
    for e in seeds: weight[e] = 3.0

    # 청크별 가중 hits + 관련 엔티티 distinct 수 + 시드 distinct 수
    hits: Dict[int, float] = {}
    rel_cnt: Dict[int, int] = {}
    seed_cnt: Dict[int, int] = {}
    seed_set = set(seeds)
    for e, w in weight.items():
        for ci in entity_chunks.get(e, []):
            hits[ci] = hits.get(ci, 0.0) + w
            rel_cnt[ci] = rel_cnt.get(ci, 0) + 1
            if e in seed_set:
                seed_cnt[ci] = seed_cnt.get(ci, 0) + 1

    # 청크별 전체 엔티티 수 (focus 분모)
    total_ent: Dict[int, int] = {}
    for chunks in entity_chunks.values():
        for ci in chunks:
            total_ent[ci] = total_ent.get(ci, 0) + 1

    def focus(ci):
        return rel_cnt.get(ci, 0) / total_ent.get(ci, 1)

    # min_rel: 질문 '시드' 엔티티가 min_rel개 이상 든 청크만 (= 관계청크). neighbor/distractor 패딩 제거.
    # 시드 2개가 같이 든 청크가 없는 질문(비관계)엔 그래프가 거의 침묵 → 그 질문 희석 0 (자연 라우팅).
    cands = [ci for ci in hits if seed_cnt.get(ci, 0) >= min_rel]
    ranked = sorted(cands,
                    key=lambda ci: (hits[ci], focus(ci),
                                    cosine(query_emb, chunk_emb[ci]) if ci in chunk_emb else -1.0),
                    reverse=True)
    return ranked[:top_k]
