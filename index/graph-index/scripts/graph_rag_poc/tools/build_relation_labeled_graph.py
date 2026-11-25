"""관계라벨 그래프 — real 관계쌍(97)을 라벨 엣지로, real 엔티티→real청크만(깨끗).
relation 정공법(검색단계서 관계 활용) + distractor 정리를 동시 테스트.
lazy 그래프(1164엔티티·9571 co-occur 엣지·84% distractor)와 대비.

graph_rag 호환 형식: entity_chunks / entity_types / edges(source,target,relation,weight) / communities
출력: data/graphs/relation_labeled_real.json
"""
import json

CORPUS = "data/chunks/scaled_1000.json"
RELS = "data/graphs/relation_summaries_real.json"
COMM = "data/graphs/community_summaries_real.json"
LAZY = "data/graphs/gliner2/lazy_community_1000.json"
OUT = "data/graphs/relation_labeled_real.json"
REAL = list(range(40))


def main():
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    rels = json.load(open(RELS, encoding="utf-8"))
    lazy = json.load(open(LAZY, encoding="utf-8"))
    real_text = {ci: corpus[ci].get("text", "") for ci in REAL}

    # 관계쌍 엔티티 수집
    ents = set()
    for o in rels:
        ents.update(o["entities"])

    # entity_chunks: real청크 중 엔티티명 포함 (깨끗 — distractor 제외)
    entity_chunks = {}
    for e in ents:
        chs = [ci for ci in REAL if e in real_text[ci]]
        if chs:
            entity_chunks[e] = chs
    # entity_types: lazy에서 가져오되 없으면 기타
    lazy_types = lazy.get("entity_types", {})
    entity_types = {e: lazy_types.get(e, "기타") for e in entity_chunks}

    # edges: 관계쌍을 라벨 엣지로 (양끝 다 entity_chunks에 있을 때)
    edges = []
    for o in rels:
        a, b = o["entities"]
        if a in entity_chunks and b in entity_chunks:
            edges.append({"source": a, "target": b, "relation": o.get("relation", "관계"), "weight": 1})

    # communities: real 커뮤니티 요약 재사용(있으면)
    communities = []
    try:
        comm = json.load(open(COMM, encoding="utf-8"))
        for c in comm:
            members = [m for m in c.get("members", []) if m in entity_chunks]
            communities.append({"id": c["id"], "size": len(members), "members": members,
                                "chunks": [ci for ci in c.get("chunks", []) if ci in REAL]})
    except FileNotFoundError:
        pass

    out = {"meta": {"source": "relation_labeled_real", "note": "real 관계쌍 라벨엣지 + real청크만(깨끗)",
                    "n_entities": len(entity_chunks), "n_edges": len(edges)},
           "entity_chunks": entity_chunks, "entity_types": entity_types,
           "edges": edges, "communities": communities}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"관계라벨 그래프: 엔티티 {len(entity_chunks)} / 라벨엣지 {len(edges)} / 커뮤니티 {len(communities)} → {OUT}")
    print("  엣지 샘플:", [f"{e['source']}-[{e['relation']}]-{e['target']}" for e in edges[:6]])


if __name__ == "__main__":
    main()
