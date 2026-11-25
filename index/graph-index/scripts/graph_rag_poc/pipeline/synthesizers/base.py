"""Synthesizer 공통 인터페이스 + 컨텍스트 빌더 helper.

각 synthesizer는 함수 형태:
    synthesize(question, candidates, chunks_db, **state) -> result_dict
return: {answer, retrieved_chunks, usage, llm_calls, ...추가필드}
"""
from typing import Callable, Dict, List


SYNTHESIZERS: Dict[str, Callable] = {}


def register(name: str):
    def wrap(fn):
        SYNTHESIZERS[name] = fn
        return fn
    return wrap


def build_plain_context(chunk_indexes: List[int],
                        chunks_db: Dict[int, Dict],
                        max_chars_per_chunk: int = 700) -> str:
    """청크 텍스트들을 [chunk N, pP] 헤더로 묶은 단일 컨텍스트 문자열.

    이전: evaluate.py: build_plain_context
    """
    lines = ["[원문 컨텍스트]"]
    for ci in chunk_indexes:
        c = chunks_db.get(ci)
        if not c:
            continue
        text = (c.get("text") or "").strip()
        if len(text) > max_chars_per_chunk:
            text = text[:max_chars_per_chunk] + " ..."
        page = c.get("page_start")
        lines.append(f"\n[chunk {ci}, p{page}]\n{text}")
    return "\n".join(lines)


def numbered_chunks(idxs: List[int], chunks_db: Dict[int, Dict], max_chars: int = 600) -> str:
    """[chunk N] 헤더 + 본문 (relevance 필터·claim 추출 입력용).

    이전: eval_real_lazy.py: _numbered_chunks
    """
    parts = []
    for ci in idxs:
        c = chunks_db.get(ci)
        if not c:
            continue
        t = (c.get("text") or "").strip()
        if len(t) > max_chars:
            t = t[:max_chars] + " ..."
        parts.append(f"[chunk {ci}]\n{t}")
    return "\n\n".join(parts)
