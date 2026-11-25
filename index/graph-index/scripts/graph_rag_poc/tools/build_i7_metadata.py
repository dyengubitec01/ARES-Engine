# -*- coding: utf-8 -*-
"""I-7 (Corpus Pre-Summarization, K²RAG) 변형 빌드 — 엔티티 디스크립션 + 커뮤니티 요약을 '참고 레이어'로 생성.

Lazy(풀 청크)는 그대로 두고, 요약에서 뽑은 메타데이터를 pseudo-chunk(index 200000+)로 추가.
GLiNER2 그래프(엔티티·커뮤니티)에 LLM 요약을 입혀 값싸게 메타데이터 생성(Full 추출 17h 대신).
출력: data/chunks/scaled_1000_i7meta.json (원1000 + 메타데이터).
인프라 끊김 대비: 항목별 try/except로 부분 실패해도 진행.
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from pipeline.shared.llm import chat  # noqa: E402

DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(DIR, "data", "chunks", "scaled_1000.json")
GRAPH = os.path.join(DIR, "data", "graphs", "gliner2", "lazy_community_1000.json")
OUT = os.path.join(DIR, "data", "chunks", "scaled_1000_i7meta.json")

COMM_BASE, ENT_BASE = 200000, 210000
TOP_ENTITIES = 30
MAX_CHUNKS = 12

ENT_PROMPT = "다음은 한 엔티티가 등장하는 청크들이다. 이 엔티티가 '무엇이며 어떤 관계·역할을 가지는지' 1~2문장으로 요약하라. 핵심 사실·관계만."
COMM_PROMPT = "다음은 한 군집의 청크들이다. 이 군집이 다루는 핵심 주제·인물·관계를 2~3문장으로 요약하라."


def chunk_text(chunks_db, idxs, cap=MAX_CHUNKS):
    out = []
    for ci in idxs[:cap]:
        c = chunks_db.get(ci)
        if c:
            out.append((c.get("text") or "")[:400])
    return "\n\n".join(f"- {t}" for t in out)


def main():
    chunks = json.load(open(SRC, encoding="utf-8"))
    chunks_db = {c["chunk_index"]: c for c in chunks}
    g = json.load(open(GRAPH, encoding="utf-8"))
    entity_chunks = g["entity_chunks"]
    meta = []

    # 커뮤니티 요약
    for comm in g.get("communities", []):
        cid = comm.get("id"); members = comm.get("members", [])
        cidx = []
        for m in members:
            cidx += entity_chunks.get(m, [])
        cidx = sorted(set(cidx))
        if not cidx:
            continue
        try:
            summ, _ = chat(COMM_PROMPT, f"[군집 청크]\n{chunk_text(chunks_db, cidx)}", max_tokens=300)
            meta.append({"chunk_index": COMM_BASE + cid, "text": f"[커뮤니티 요약 {cid}] {summ.strip()}",
                         "page_start": None, "i7_meta": "community"})
            print(f"  community {cid} ({len(members)}멤버) → 요약 OK")
        except Exception as e:
            print(f"  community {cid} 실패: {str(e)[:50]}")

    # 엔티티 디스크립션 (청크 많은 상위)
    top = sorted(entity_chunks.items(), key=lambda kv: len(kv[1]), reverse=True)[:TOP_ENTITIES]
    for i, (ent, idxs) in enumerate(top):
        try:
            desc, _ = chat(ENT_PROMPT, f"[엔티티] {ent}\n[청크]\n{chunk_text(chunks_db, sorted(idxs))}", max_tokens=200)
            meta.append({"chunk_index": ENT_BASE + i, "text": f"[엔티티 디스크립션] {ent}: {desc.strip()}",
                         "page_start": None, "i7_meta": "entity", "entity": ent})
            print(f"  entity '{ent}' ({len(idxs)}청크) → 디스크립션 OK")
        except Exception as e:
            print(f"  entity '{ent}' 실패: {str(e)[:50]}")

    merged = chunks + meta
    json.dump(merged, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n저장: {OUT}  (원{len(chunks)} + 메타{len(meta)} = {len(merged)})")
    print(f"  메타 구성: 커뮤니티 {sum(1 for m in meta if m['i7_meta']=='community')} + 엔티티 {sum(1 for m in meta if m['i7_meta']=='entity')}")


if __name__ == "__main__":
    main()
