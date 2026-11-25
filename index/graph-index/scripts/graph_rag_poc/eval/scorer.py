"""답변 자동 채점 — keyword 포함률 + chunk recall + 환각 키워드 페널티.

이전: scripts/graph_rag_poc/_shared/lazy_value_test/evaluate.py: score_answer
"""
from typing import Any, Dict, List


def score_answer(result: Dict[str, Any], qa: Dict[str, Any]) -> Dict[str, Any]:
    """단일 트랙의 답변 결과를 채점.

    result: {"answer": str, "retrieved_chunks": list[int], "usage": dict, ...}
    qa:     {"answer_must_contain": list[str], "answer_must_not_contain": list[str],
             "required_chunks": list[int], ...}
    return: {keyword_score, keyword_hits, chunk_recall, hallucination_free, ...}
    """
    answer = (result.get("answer") or "").lower()
    must = qa.get("answer_must_contain", [])
    must_not = qa.get("answer_must_not_contain", [])
    required = set(qa.get("required_chunks", []))
    retrieved = set(result.get("retrieved_chunks", []))

    # 1. 키워드 포함률
    hit = sum(1 for kw in must if kw.lower() in answer)
    keyword_score = hit / max(len(must), 1)

    # 2. 필수 청크 recall
    chunk_recall = (len(required & retrieved) / max(len(required), 1)) if required else 1.0

    # 3. 환각 키워드 (있으면 안 되는 단어) — 페널티
    halluc_hits = [kw for kw in must_not if kw.lower() in answer]
    hallucination_free = len(halluc_hits) == 0

    # 4. 답변 길이
    answer_chars = len(result.get("answer") or "")

    return {
        "keyword_score": round(keyword_score, 3),
        "keyword_hits": f"{hit}/{len(must)}",
        "chunk_recall": round(chunk_recall, 3),
        "hallucination_free": hallucination_free,
        "hallucination_hits": halluc_hits,
        "required_chunks": sorted(required),
        "retrieved_chunks_count": len(retrieved),
        "answer_chars": answer_chars,
        "input_tokens": result.get("usage", {}).get("prompt_tokens", 0),
        "output_tokens": result.get("usage", {}).get("completion_tokens", 0),
    }


def recall_at_k(retrieved: List[int], required: List[int], k: int) -> float:
    """top-k 청크 중 required 청크 포함률."""
    if not required:
        return 1.0
    return round(len(set(retrieved[:k]) & set(required)) / len(required), 3)
