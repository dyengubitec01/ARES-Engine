"""I-7(청크 요약) 방식 — 단 '관계'에 타깃. real청크(40개)에서 명시된 인물·조직·제품 관계를
LLM으로 추출/요약 → 엔티티쌍별 관계요약. (엔티티 설명 아님 = I-7 기각분과 구분)

출력: data/graphs/relation_summaries_real.json = [{"entities":[a,b], "relation":..., "summary":...}]
검색 축(R-5 등)과 직교한 '구조 축' 보강 — 스택에 얹어 테스트(relation_inject stage).
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.shared.llm import chat  # noqa: E402

CORPUS = "data/chunks/scaled_1000.json"
OUT = "data/graphs/relation_summaries_real.json"

SYS = """다음 텍스트에 **명시적으로 서술된** 인물·조직·제품 사이의 관계만 추출하라. 추측·암시는 금지.
각 관계를 JSON 배열로 출력:
[{"a":"대상1","b":"대상2","relation":"관계유형(사제/동료/영입/보고라인/소속/공동창업/협력/경쟁/투자 등)","summary":"근거를 1문장으로 요약"}]
- 단순 동시등장·우연한 언급은 제외(실제 관계가 서술된 것만).
- 관계가 없으면 [] 출력. JSON만, 설명 없이."""


def parse(content):
    m = re.search(r"\[.*\]", content, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group())
    except Exception:
        return []


def main():
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    real = [c for c in corpus if c.get("category") != "distractor"]
    print(f"real 청크 {len(real)}개에서 관계 추출...")
    pairs = {}  # (a,b) sorted -> {relation set, summaries[]}
    for c in real:
        txt = c.get("text", "")
        content, _ = chat(SYS, f"[텍스트]\n{txt}", max_tokens=500)
        for rel in parse(content):
            a, b = (rel.get("a") or "").strip(), (rel.get("b") or "").strip()
            if not a or not b or a == b:
                continue
            key = tuple(sorted([a, b]))
            d = pairs.setdefault(key, {"relations": set(), "summaries": []})
            if rel.get("relation"):
                d["relations"].add(rel["relation"].strip())
            if rel.get("summary"):
                d["summaries"].append(rel["summary"].strip())
    out = []
    for (a, b), d in pairs.items():
        relstr = "·".join(sorted(d["relations"])) or "관계"
        # 중복 요약 dedup, 최대 3문장
        seen, sums = set(), []
        for s in d["summaries"]:
            if s not in seen:
                seen.add(s)
                sums.append(s)
        summary = f"{a} ↔ {b} [{relstr}]: " + " ".join(sums[:3])
        out.append({"entities": [a, b], "relation": relstr, "summary": summary})
    out.sort(key=lambda x: x["entities"])
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"관계요약 {len(out)}쌍 → {OUT}")
    for o in out[:8]:
        print("  -", o["summary"][:100])


if __name__ == "__main__":
    main()
