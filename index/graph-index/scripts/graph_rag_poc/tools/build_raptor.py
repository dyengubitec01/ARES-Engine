# -*- coding: utf-8 -*-
"""RAPTOR(I-5) 빌드 — 청크 k-means 클러스터링 → 클러스터별 LLM 요약 → 요약 pseudo-chunk 병합.

collapsed-tree 1레벨 근사: leaves(원청크) + 1개 요약 레벨.
출력: data/chunks/scaled_1000_raptor.json (원청크 + 요약, 요약은 chunk_index 100000+).
요약 pseudo-chunk를 회수 풀에 추가하면 global/집계 질문에서 도움 되는지 테스트(I-5).
"""
import json
import os
import sys

import numpy as np
from sklearn.cluster import KMeans

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from pipeline.shared.embedding import embed_chunks  # noqa: E402
from pipeline.shared.llm import chat  # noqa: E402

DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(DIR, "data", "chunks", "scaled_1000.json")
OUT = os.path.join(DIR, "data", "chunks", "scaled_1000_raptor.json")
N_CLUSTERS = 40
SUMMARY_BASE_INDEX = 100000
MAX_CHUNKS_PER_SUMMARY = 12

SUMM_PROMPT = "다음 여러 청크를 하나의 요약으로 압축하라. 핵심 사실·인물·기관·관계·수치를 빠짐없이 보존하고, 군더더기는 제거하라."


def main():
    chunks = json.load(open(SRC, encoding="utf-8"))
    print(f"원청크 {len(chunks)}개 임베딩...")
    emb = embed_chunks(chunks)
    idx = [c["chunk_index"] for c in chunks]
    X = np.array([emb[i] for i in idx])

    print(f"k-means {N_CLUSTERS} 클러스터...")
    labels = KMeans(n_clusters=N_CLUSTERS, n_init=4, random_state=0).fit_predict(X)
    by_cluster = {}
    for c, lb in zip(chunks, labels):
        by_cluster.setdefault(int(lb), []).append(c)

    summaries = []
    for lb, cs in sorted(by_cluster.items()):
        texts = [(c.get("text") or "")[:500] for c in cs[:MAX_CHUNKS_PER_SUMMARY]]
        body = "\n\n".join(f"- {t}" for t in texts)
        summ, _ = chat(SUMM_PROMPT, f"[청크 {len(cs)}개]\n{body}", max_tokens=400)
        summaries.append({
            "chunk_index": SUMMARY_BASE_INDEX + lb,
            "text": f"[요약] {summ.strip()}",
            "page_start": None, "raptor_summary": True, "cluster_size": len(cs),
        })
        print(f"  cluster {lb}: {len(cs)}청크 → 요약 {len(summ)}자")

    merged = chunks + summaries
    json.dump(merged, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"저장: {OUT}  (원{len(chunks)} + 요약{len(summaries)} = {len(merged)})")


if __name__ == "__main__":
    main()
