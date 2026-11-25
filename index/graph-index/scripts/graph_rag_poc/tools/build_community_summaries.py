"""I-6/커뮤니티 요약 — real 서브그래프에서 커뮤니티 검출 → 각 커뮤니티를 청크 종합 요약.
sensemaking/global 질문 타깃(MS GraphRAG식). lazy 그래프 커뮤니티는 distractor 오염이라 재사용 불가 → real만.

출력: data/graphs/community_summaries_real.json = [{"id", "members":[...], "summary": ...}]
"""
import json
import os
import sys

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.shared.llm import chat  # noqa: E402

CORPUS = "data/chunks/scaled_1000.json"
GRAPH = "data/graphs/gliner2/lazy_community_1000.json"
OUT = "data/graphs/community_summaries_real.json"
REAL = set(range(40))

SYS = """다음은 한 주제 그룹에 속한 문서 조각들이다. 이 그룹이 무엇에 관한 것인지 **종합 요약**하라.
- 핵심 주제(팀/조직/기술/철학/관계 등)와 그 그룹의 주요 사실·구조를 3~5문장으로.
- 텍스트에 있는 내용만. 추측 금지. 요약문만 출력."""


def ends(e):
    return (e["source"], e["target"]) if isinstance(e, dict) else (e[0], e[1])


def main():
    g = json.load(open(GRAPH, encoding="utf-8"))
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    ec = g["entity_chunks"]
    real_ents = {e for e, chs in ec.items() if set(chs) & REAL}
    # real 서브그래프 (양끝 real, 자기 자신 제외)
    G = nx.Graph()
    G.add_nodes_from(real_ents)
    for e in g["edges"]:
        s, t = ends(e)
        if s in real_ents and t in real_ents and s != t:
            w = e.get("weight", 1) if isinstance(e, dict) else 1
            G.add_edge(s, t, weight=w)
    comms = nx.community.greedy_modularity_communities(G, weight="weight")
    print(f"real 엔티티 {len(real_ents)} → 커뮤니티 {len(comms)}개")
    out = []
    for i, c in enumerate(comms):
        members = sorted(c)
        if len(members) < 3:
            continue
        # 멤버들의 real 청크 모으기
        chunk_ids = sorted({ci for m in members for ci in ec.get(m, []) if ci in REAL})
        if not chunk_ids:
            continue
        texts = []
        for ci in chunk_ids[:14]:
            texts.append(corpus[ci].get("text", "")[:600])
        content, _ = chat(SYS, "[문서 조각들]\n" + "\n---\n".join(texts), max_tokens=400)
        out.append({"id": i, "size": len(members),
                    "members": members[:25], "chunks": chunk_ids, "summary": content.strip()})
        print(f"  C{i} ({len(members)}엔티티·{len(chunk_ids)}청크): {content.strip()[:90]}")
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n커뮤니티 요약 {len(out)}개 → {OUT}")


if __name__ == "__main__":
    main()
