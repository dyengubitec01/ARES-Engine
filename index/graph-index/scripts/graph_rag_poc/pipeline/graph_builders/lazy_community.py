"""LazyGraphRAG 변형: GLiNER2 엔티티 출력 → 공출현 엣지 + Louvain 커뮤니티 (LLM 0회)

기존 GLiNER2 결과(extracted_entities_gliner2.json)에서 엔티티만 재활용.
관계 라벨은 버리고, 공출현으로 엣지 재생성 후 Louvain으로 커뮤니티 형성.

실행:
  python scripts/graph_rag_poc/build_lazy_community.py
출력:
  data/lazy_community.json
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

import networkx as nx  # noqa: E402
from networkx.algorithms.community import louvain_communities  # noqa: E402

from pipeline.shared.config import GRAPHS_DIR  # noqa: E402


def normalize_name(name: str) -> str:
    return (name or "").strip()


def build(input_path: str, output_path: str, min_entity_len: int) -> None:
    data = json.load(open(input_path, encoding="utf-8"))
    results = data["results"]

    # 1. 엔티티 → source_chunks, 청크 → 엔티티, 엔티티 → 타입 (관계 라벨 무시)
    entity_chunks: dict[str, set[int]] = defaultdict(set)
    chunk_entities: dict[int, set[str]] = defaultdict(set)
    entity_type_votes: dict[str, Counter] = defaultdict(Counter)
    for r in results:
        cid = r["chunk_index"]
        for ent in r["extracted"]["entities"]:
            name = normalize_name(ent["name"])
            if len(name) < min_entity_len:
                continue
            entity_chunks[name].add(cid)
            chunk_entities[cid].add(name)
            entity_type_votes[name][ent.get("type", "OTHER")] += 1

    # 대표 타입 = 최빈 타입
    entity_type: dict[str, str] = {
        name: votes.most_common(1)[0][0] for name, votes in entity_type_votes.items()
    }
    print(f"[1] Entities: {len(entity_chunks)} unique, in {len(chunk_entities)} chunks")

    # 2. 공출현 엣지 (같은 청크에 함께 등장한 쌍, 가중치 = 공출현 횟수)
    edge_weight: dict[tuple[str, str], int] = defaultdict(int)
    for cid, ents in chunk_entities.items():
        for a, b in combinations(sorted(ents), 2):
            edge_weight[(a, b)] += 1

    print(f"[2] Co-occurrence edges: {len(edge_weight)}")

    # 3. Louvain 커뮤니티
    G = nx.Graph()
    for (a, b), w in edge_weight.items():
        G.add_edge(a, b, weight=w)
    # 고립 엔티티 (다른 엔티티와 공출현 없음)도 노드로 포함
    for ent in entity_chunks:
        if ent not in G:
            G.add_node(ent)

    communities = louvain_communities(G, weight="weight", seed=42)
    communities.sort(key=lambda c: -len(c))
    print(f"[3] Communities (Louvain): {len(communities)}")
    print(f"    sizes (top 10): {[len(c) for c in communities[:10]]}")

    # 4. JSON 직렬화
    out = {
        "meta": {
            "source": os.path.basename(input_path),
            "entity_count": len(entity_chunks),
            "edge_count": len(edge_weight),
            "community_count": len(communities),
            "min_entity_len": min_entity_len,
        },
        "entity_chunks": {ent: sorted(cs) for ent, cs in entity_chunks.items()},
        "entity_types": entity_type,
        "edges": [
            {"source": a, "target": b, "weight": w}
            for (a, b), w in sorted(edge_weight.items(), key=lambda x: -x[1])
        ],
        "communities": [
            {
                "id": i,
                "size": len(comm),
                "members": sorted(comm),
                "chunks": sorted({c for ent in comm for c in entity_chunks[ent]}),
            }
            for i, comm in enumerate(communities)
        ],
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    json.dump(out, open(output_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[4] Saved → {output_path}")

    # 미리보기: 가장 큰 커뮤니티 3개
    print("\n  상위 3개 커뮤니티 미리보기:")
    for c in out["communities"][:3]:
        members_preview = ", ".join(c["members"][:8])
        print(f"    C{c['id']} (size={c['size']}, chunks={len(c['chunks'])}): {members_preview}...")


def main() -> int:
    p = argparse.ArgumentParser(description="LazyGraphRAG 변형 (GLiNER2 기반)")
    p.add_argument("--input", default=os.path.join(GRAPHS_DIR, "gliner2", "extracted_40.json"))
    p.add_argument("--output", default=os.path.join(GRAPHS_DIR, "gliner2", "lazy_community_40.json"))
    p.add_argument("--min-entity-len", type=int, default=2,
                   help="최소 엔티티 글자 수 (기본 2 - 너무 짧은 노이즈 제거)")
    args = p.parse_args()

    if not os.path.exists(args.input):
        print(f"입력 파일 없음: {args.input}", file=sys.stderr)
        return 1
    build(args.input, args.output, args.min_entity_len)
    return 0


if __name__ == "__main__":
    sys.exit(main())
