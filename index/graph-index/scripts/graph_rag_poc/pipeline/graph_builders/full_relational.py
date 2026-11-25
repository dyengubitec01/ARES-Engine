"""Gemma27B 풀 활용 그래프 빌더 — 1번(리소스 많은 LLM 기반) 그래프 PoC용.

PoC 정의 (사용자 정리):
  1번 = "거대 언어모델을 이용한, 리소스가 많이 들어가는 그래프"  ← 이 빌더
  2번 = LazyGraphRAG (GLiNER2 기반 경량)              ← build_lazy_community.py
  비교: 2번이 1번에 근접하면 성공.

→ 1번 그래프는 Gemma 50분 추출 산출물(엔티티/관계 라벨/디스크립션)을 모두 보존해야
   "풀 활용 vs 경량" 정직 비교가 됨.

입력 : data/extracted_entities.json (extract_entities.py 산출물)
출력 : data/graph_community.json (lazy_community.json **확장** 스키마)
       - 기본 필드는 query_lazy.py 호환 (entity_chunks/entity_types/edges/communities)
       - 추가 필드: entity_descriptions, relation_edges (관계 라벨 + 디스크립션 + 청크 출처)

Louvain 입력 가중치:
  공출현 가중치 + (관계 엣지 가중치 × relation_weight_factor)
  → 공출현 9k vs 관계 ~0.4k라 관계가 묻히지 않도록 기본 factor=1.0 (조정 가능)

실행:
  python scripts/graph_rag_poc/gemma3-27b/build_graph.py
  python scripts/graph_rag_poc/gemma3-27b/build_graph.py \
    --no-validation --output data/graph_community_20260522.json
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

import networkx as nx  # noqa: E402
from networkx.algorithms.community import louvain_communities  # noqa: E402

from pipeline.shared.config import CHUNKS_DIR, GRAPHS_DIR  # noqa: E402


# 타입 동점 시 우선순위 (왼쪽이 높음)
TYPE_PRIORITY = [
    "ORG", "PERSON", "LOCATION", "PROJECT",
    "STANDARD", "SYSTEM", "PRODUCT",
    "CONCEPT", "EVENT", "OTHER", "DATA",
]

# 관계 타입 정규화 (영어·구두점 섞인 표기 → 한글 대표어)
RELATION_MAP = {
    "HAS_DATA": "보유",
    "CONTAINS": "포함",
    "HAS_COMPONENT": "구성",
    "HAS_PART": "구성",
    "COMPONENT_OF": "구성",
    "IS_PART_OF": "구성",
    "PART_OF": "구성",
    "USES": "사용",
    "USED_FOR": "용도",
    "RELATED": "관련",
    "RELATED_TO": "관련",
    "COLLABORATES_WITH": "협력",
    "DEVELOPED_BY": "개발",
    "DEPLOYED_ON": "배포",
    "IMPLEMENTED_BY": "구축",
    "PROJECT_OWNER": "소유",
}


def normalize_name(name: str) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", " ", name.strip())


def consolidate_type(type_counter: Counter) -> str:
    if not type_counter:
        return "OTHER"
    max_count = max(type_counter.values())
    candidates = [t for t, c in type_counter.items() if c == max_count]
    if len(candidates) == 1:
        return candidates[0]
    for t in TYPE_PRIORITY:
        if t in candidates:
            return t
    return candidates[0]


def normalize_relation_type(rtype: str) -> str:
    if not rtype:
        return "관련"
    return RELATION_MAP.get(rtype.upper().strip(), rtype.strip())


def load_chunks_text(path: str) -> Dict[int, str]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        arr = json.load(f)
    return {c["chunk_index"]: c.get("text", "") for c in arr if c.get("chunk_index") is not None}


def build(
    extracted_path: str,
    output_path: str,
    chunks_path: str,
    strict_validation: bool,
    min_entity_len: int,
    relation_weight_factor: float,
) -> None:
    with open(extracted_path, encoding="utf-8") as f:
        data = json.load(f)

    chunks_text = load_chunks_text(chunks_path) if strict_validation else {}
    if strict_validation and not chunks_text:
        print(f"경고: {chunks_path} 로드 실패 - 환각 검증 비활성화", file=sys.stderr)
        strict_validation = False

    results = data.get("results", [])

    # ────────── 1. 엔티티 수집 (Gemma 풀: 타입/디스크립션/원본 이름 모두 보존) ──────────
    entity_type_votes: Dict[str, Counter] = defaultdict(Counter)
    entity_chunks: Dict[str, set] = defaultdict(set)
    entity_descriptions: Dict[str, List[str]] = defaultdict(list)
    orig_names: Dict[str, Counter] = defaultdict(Counter)
    chunk_entities: Dict[int, set] = defaultdict(set)

    # ────────── 2. 관계 엣지 수집 (Gemma 라벨 + 디스크립션, 환각 검증) ──────────
    relation_data: Dict[tuple, Dict[str, Any]] = {}

    chunks_processed = 0
    chunks_skipped = 0
    relations_kept = 0
    hallucination_filtered = 0

    for r in results:
        if "error" in r:
            chunks_skipped += 1
            continue
        ext = r.get("extracted") or {}
        if ext.get("_parse_error"):
            chunks_skipped += 1
            continue
        ci = r.get("chunk_index")
        if ci is None:
            continue
        chunks_processed += 1
        chunk_text = chunks_text.get(ci, "") if strict_validation else None

        local_norm: Dict[str, str] = {}  # raw → norm 매핑 (관계 해석용)
        for e in ext.get("entities", []) or []:
            raw = e.get("name") or ""
            norm = normalize_name(raw)
            if len(norm) < min_entity_len:
                continue
            etype = e.get("type") or "OTHER"
            desc = (e.get("description") or "").strip()
            entity_type_votes[norm][etype] += 1
            entity_chunks[norm].add(int(ci))
            chunk_entities[int(ci)].add(norm)
            orig_names[norm][raw] += 1
            if desc and desc not in entity_descriptions[norm]:
                entity_descriptions[norm].append(desc)
            local_norm[raw] = norm

        for rel in ext.get("relations", []) or []:
            src_raw = rel.get("source")
            tgt_raw = rel.get("target")
            if not src_raw or not tgt_raw:
                continue
            # 환각 검증: source/target 둘 다 청크 본문에 등장해야 함
            if strict_validation and chunk_text:
                if src_raw not in chunk_text or tgt_raw not in chunk_text:
                    hallucination_filtered += 1
                    continue
            src = local_norm.get(src_raw) or normalize_name(src_raw)
            tgt = local_norm.get(tgt_raw) or normalize_name(tgt_raw)
            if not src or not tgt or src == tgt:
                continue
            if src not in entity_type_votes or tgt not in entity_type_votes:
                continue
            rtype = normalize_relation_type(rel.get("type") or "관련")
            # 정렬된 키로 무방향 통합 (Louvain은 무방향이므로)
            key = tuple(sorted([src, tgt]))
            if key not in relation_data:
                relation_data[key] = {
                    "relation_types": Counter(),
                    "source_chunks": set(),
                    "descriptions": [],
                }
            relation_data[key]["relation_types"][rtype] += 1
            relation_data[key]["source_chunks"].add(int(ci))
            rdesc = (rel.get("description") or "").strip()
            if rdesc and len(relation_data[key]["descriptions"]) < 5:
                relation_data[key]["descriptions"].append(rdesc)
            relations_kept += 1

    # 대표 타입
    entity_type = {name: consolidate_type(v) for name, v in entity_type_votes.items()}

    # ────────── 3. 공출현 엣지 ──────────
    cooccur_weight: Dict[tuple, int] = defaultdict(int)
    for cid, ents in chunk_entities.items():
        for a, b in combinations(sorted(ents), 2):
            cooccur_weight[(a, b)] += 1

    # ────────── 4. Louvain — 공출현 + 관계 가중치 통합 그래프 ──────────
    G = nx.Graph()
    for (a, b), w in cooccur_weight.items():
        G.add_edge(a, b, weight=float(w))
    for key, info in relation_data.items():
        rw = sum(info["relation_types"].values()) * relation_weight_factor
        if G.has_edge(*key):
            G[key[0]][key[1]]["weight"] += rw
        else:
            G.add_edge(key[0], key[1], weight=float(rw))
    for ent in entity_type:
        if ent not in G:
            G.add_node(ent)

    communities = louvain_communities(G, weight="weight", seed=42)
    communities.sort(key=lambda c: -len(c))

    # ────────── 5. 콘솔 통계 ──────────
    print("=" * 60)
    print("Gemma27B 풀 활용 그래프 빌드")
    print("=" * 60)
    print(f"처리 청크: {chunks_processed}개 (스킵 {chunks_skipped}: error/parse_error)")
    if strict_validation:
        total = relations_kept + hallucination_filtered
        ratio = 100 * hallucination_filtered / max(total, 1)
        print(f"본문 검증: 통과 {relations_kept}, 환각 차단 "
              f"{hallucination_filtered}/{total} ({ratio:.1f}%)")
    else:
        print("본문 검증: 비활성화 (--no-validation)")
    print(f"엔티티(노드): {len(entity_type)}, 디스크립션 보유: "
          f"{sum(1 for v in entity_descriptions.values() if v)}")
    print(f"관계 엣지 (Gemma 라벨): {len(relation_data)}")
    print(f"공출현 엣지: {len(cooccur_weight)}")
    print(f"통합 엣지 (Louvain 입력): {G.number_of_edges()}, "
          f"노드: {G.number_of_nodes()}")
    print(f"커뮤니티(Louvain): {len(communities)}, "
          f"sizes(top 10): {[len(c) for c in communities[:10]]}")

    # ────────── 6. lazy 호환 + 풀 정보 확장 스키마 직렬화 ──────────
    out = {
        "meta": {
            "source": os.path.basename(extracted_path),
            "builder": "gemma3-27b/build_graph.py",
            "mode": "gemma_full_plus_cooccurrence",
            "entity_count": len(entity_type),
            "edge_count": len(cooccur_weight),         # query_lazy 호환 (공출현 엣지 수)
            "relation_edge_count": len(relation_data), # 신규: Gemma 관계 엣지 수
            "community_count": len(communities),
            "min_entity_len": min_entity_len,
            "strict_validation": strict_validation,
            "hallucination_filtered": hallucination_filtered,
            "relations_kept": relations_kept,
            "relation_weight_factor": relation_weight_factor,
        },
        "entity_chunks": {ent: sorted(cs) for ent, cs in entity_chunks.items()},
        "entity_types": entity_type,
        # 신규: Gemma 디스크립션 보존
        "entity_descriptions": {ent: descs for ent, descs in entity_descriptions.items() if descs},
        "entity_display_names": {ent: orig_names[ent].most_common(1)[0][0]
                                  for ent in entity_type},
        # query_lazy 호환: 공출현 엣지를 edges에 그대로
        "edges": [
            {"source": a, "target": b, "weight": w}
            for (a, b), w in sorted(cooccur_weight.items(), key=lambda x: -x[1])
        ],
        # 신규: Gemma가 명시한 관계 엣지 + 라벨 + 디스크립션
        "relation_edges": [
            {
                "source": a,
                "target": b,
                "type": info["relation_types"].most_common(1)[0][0],
                "relation_types": dict(info["relation_types"]),
                "descriptions": info["descriptions"],
                "source_chunks": sorted(info["source_chunks"]),
                "weight": sum(info["relation_types"].values()),
            }
            for (a, b), info in sorted(
                relation_data.items(),
                key=lambda x: -sum(x[1]["relation_types"].values()),
            )
        ],
        "communities": [
            {
                "id": i,
                "size": len(comm),
                "members": sorted(comm),
                "chunks": sorted({c for ent in comm for c in entity_chunks.get(ent, [])}),
            }
            for i, comm in enumerate(communities)
        ],
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    json.dump(out, open(output_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n저장 → {output_path}")

    print("\n  상위 3개 커뮤니티 미리보기:")
    for c in out["communities"][:3]:
        members_preview = ", ".join(c["members"][:8])
        print(f"    C{c['id']} (size={c['size']}, chunks={len(c['chunks'])}): "
              f"{members_preview}...")


def main() -> int:
    p = argparse.ArgumentParser(
        description="Gemma27B 풀 활용 그래프 (엔티티+관계 라벨+디스크립션+공출현)"
    )
    p.add_argument("--input", default=os.path.join(GRAPHS_DIR, "gemma3", "extracted_40.json"))
    p.add_argument("--output", default=os.path.join(GRAPHS_DIR, "gemma3", "community_40.json"))
    p.add_argument("--chunks", default=os.path.join(CHUNKS_DIR, "golden_40.json"),
                   help="원문 청크 JSON (관계 환각 검증용)")
    p.add_argument("--no-validation", action="store_true", help="환각 검증 비활성화")
    p.add_argument("--min-entity-len", type=int, default=2)
    p.add_argument("--relation-weight-factor", type=float, default=1.0,
                   help="Louvain 가중치에서 관계 엣지 배수 (기본 1.0)")
    args = p.parse_args()

    if not os.path.exists(args.input):
        print(f"입력 파일 없음: {args.input}", file=sys.stderr)
        return 1
    build(
        args.input,
        args.output,
        args.chunks,
        strict_validation=not args.no_validation,
        min_entity_len=args.min_entity_len,
        relation_weight_factor=args.relation_weight_factor,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
