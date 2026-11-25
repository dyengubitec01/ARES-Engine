# -*- coding: utf-8 -*-
"""엔티티 정규화 — 분절된 변형 키를 정식 엔티티 하나로 병합.

문제: gliner2가 1인을 5~8개 키로 쪼갬(정민호/정민호이며/정민호 대표/...) → entity_chunks 분산 +
      변형끼리 junk 엣지(Autonova↔Autonova의). traversal·linking 오염.
정규화:
  - PERSON: 첫 토큰 + 조사제거 = 정식 이름 (정민호 대표→정민호, 정민호이며→정민호).
  - 그 외: 끝 조사만 제거 (Autonova의→Autonova, 단 'Autonova 본사'는 그대로=구별 유지).
  - entity_chunks = 정식별 union, edges = 정식으로 remap(self-loop=변형엣지 제거, weight 합산).
출력: data/graphs/gliner2/lazy_community_1000_canon.json
"""
import collections
import json
import os

DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(DIR, "data", "graphs", "gliner2", "lazy_community_1000.json")
OUT = os.path.join(DIR, "data", "graphs", "gliner2", "lazy_community_1000_canon.json")

JOSA = ("이며", "으로서", "로서", "이라는", "라는", "에서", "에게", "부터", "까지",
        "의", "은", "는", "이", "가", "을", "를", "와", "과", "도", "로", "만", "들", "에")


def strip_josa(s):
    while len(s) > 2:
        for j in sorted(JOSA, key=len, reverse=True):
            if s.endswith(j) and len(s) - len(j) >= 2:
                s = s[:-len(j)]
                break
        else:
            break
    return s


def canon(key, etype):
    if etype == "PERSON":
        head = key.split()[0] if key.split() else key   # 첫 토큰
        return strip_josa(head)
    return strip_josa(key.strip())                       # 끝 조사만


def main():
    g = json.load(open(SRC, encoding="utf-8"))
    ec = g["entity_chunks"]
    et = g.get("entity_types", {})
    edges = g.get("edges", [])
    comms = g.get("communities", [])

    # 1) 키 → 정식
    cmap = {k: canon(k, et.get(k, "")) for k in ec}
    # 2) entity_chunks union
    canon_chunks = collections.defaultdict(set)
    canon_type = {}
    for k, chs in ec.items():
        c = cmap[k]
        canon_chunks[c].update(chs)
        canon_type.setdefault(c, collections.Counter())[et.get(k, "")] += 1
    canon_chunks = {c: sorted(v) for c, v in canon_chunks.items()}
    canon_type = {c: cnt.most_common(1)[0][0] for c, cnt in canon_type.items()}

    # 3) edges remap (self/변형엣지 제거, weight 합산)
    ew = collections.defaultdict(int)
    for e in edges:
        s, t = cmap.get(e.get("source")), cmap.get(e.get("target"))
        if not s or not t or s == t:
            continue
        ew[tuple(sorted((s, t)))] += e.get("weight", 1)
    canon_edges = [{"source": a, "target": b, "weight": w} for (a, b), w in ew.items()]

    # 4) communities remap
    canon_comms = []
    for c in comms:
        mem = sorted(set(cmap.get(m, m) for m in c.get("members", [])))
        canon_comms.append({"id": c.get("id"), "members": mem})

    out = {
        "meta": {**g.get("meta", {}), "canonicalized": True,
                 "entity_count": len(canon_chunks), "edge_count": len(canon_edges)},
        "entity_chunks": canon_chunks, "entity_types": canon_type,
        "edges": canon_edges, "communities": canon_comms,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)

    # ---- 리포트 ----
    print(f"엔티티: {len(ec)} → {len(canon_chunks)} (병합 {len(ec)-len(canon_chunks)})")
    print(f"엣지: {len(edges)} → {len(canon_edges)} (변형/중복 제거 {len(edges)-len(canon_edges)})")
    print("\n[병합 확인] 핵심 인물:")
    for p in ["정민호", "박서연", "강현우", "한수정", "오태경", "송지윤"]:
        merged = [k for k in ec if cmap[k] == p]
        print(f"  {p}: {len(merged)}개 변형 → 1  (청크 {len(canon_chunks.get(p,[]))}개)")
    print("\n[관계 보존 확인]:")
    adj = collections.defaultdict(set)
    for e in canon_edges:
        adj[e["source"]].add(e["target"]); adj[e["target"]].add(e["source"])
    for a, b in [("박서연","정민호"),("박서연","강현우"),("강현우","한수정"),("김지훈","박서연"),("윤재혁","오태경")]:
        print(f"  {a}-{b}: 엣지={b in adj.get(a,())}")
    print(f"\n저장: {OUT}")


if __name__ == "__main__":
    main()
