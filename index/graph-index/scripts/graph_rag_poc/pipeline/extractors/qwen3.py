"""Qwen3-14B-Q8 (Mac Ollama)로 청크에서 엔티티·관계 추출.

기존 extract_entities.py(Gemma 27B vLLM)와 동일한 입출력 포맷을 유지.
차이점은 endpoint와 model만:
  - Gemma:   http://localhost:8000/v1/chat/completions  (vLLM)
  - Qwen3:   http://localhost:11434/v1/chat/completions  (Ollama OpenAI 호환)

실행:
  .venv/Scripts/python.exe scripts/graph_rag_poc/extract_entities_qwen.py
  .venv/Scripts/python.exe scripts/graph_rag_poc/extract_entities_qwen.py --limit 5
"""
import argparse
import io
import json
import os
import sys
import time
from typing import Any, Dict, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

import requests  # noqa: E402

from pipeline.shared.config import Config as C, CHUNKS_DIR, GRAPHS_DIR  # noqa: E402


OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:14b-q8_0")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))


SYSTEM_PROMPT = """주어진 텍스트에서 엔티티와 관계를 JSON으로 추출하세요.

[필수 규칙]
1. 관계의 source와 target은 반드시 entities 리스트의 name과 정확히 일치해야 합니다.
2. 출력은 오직 유효한 JSON만. 마크다운 코드블록·부가 설명 금지.
3. 엔티티는 도메인 고유 명사·기술 용어만 포함. 일반 명사(데이터, 정보, 시스템, 건물, 파일, 관리자, 사용자 등)는 제외.

[엔티티 이름 규칙]
- 텍스트에 나온 가장 구체적·완전한 표현 사용
- 같은 청크 내에서 같은 대상은 반드시 같은 이름으로

[엔티티 타입]
ORG, PRODUCT, SYSTEM, CONCEPT, STANDARD, PROJECT, PERSON, LOCATION, EVENT, OTHER

[출력 형식]
{
  "entities": [
    {"name": "엔티티명", "type": "타입", "description": "1문장 설명"}
  ],
  "relations": [
    {"source": "엔티티명", "target": "엔티티명", "type": "관계명", "description": "1문장 설명"}
  ]
}"""


def _build_user_message(chunk: Dict[str, Any]) -> str:
    filename = chunk.get("original_filename") or "(파일명 없음)"
    page_start = chunk.get("page_start")
    page_end = chunk.get("page_end")
    chunk_index = chunk.get("chunk_index")
    text = chunk.get("text") or ""

    if page_start is not None and page_end is not None:
        page_info = f"페이지/슬라이드 {page_start}-{page_end}"
    elif page_start is not None:
        page_info = f"페이지/슬라이드 {page_start}"
    else:
        page_info = "위치 정보 없음"

    return (
        f"[문서] {filename}\n"
        f"[위치] {page_info} (chunk_index={chunk_index})\n"
        f"[내용]\n{text}"
    )


def extract_one(chunk: Dict[str, Any]) -> Tuple[Dict[str, Any], float, Dict[str, Any]]:
    """청크 1개에서 엔티티·관계 추출."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(chunk)},
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
        "stream": False,
    }

    t0 = time.time()
    r = requests.post(
        f"{OLLAMA_URL}/v1/chat/completions",
        json=payload,
        timeout=OLLAMA_TIMEOUT,
    )
    elapsed = time.time() - t0
    r.raise_for_status()
    body = r.json()

    content = body["choices"][0]["message"]["content"]
    usage = body.get("usage", {})

    parsed: Dict[str, Any]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        stripped = content.strip()
        # 코드블록 제거
        if stripped.startswith("```"):
            lines = stripped.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            stripped = "\n".join(lines)
        # qwen3는 종종 <think>...</think> 블록을 출력함 - 제거
        if "<think>" in stripped:
            end = stripped.find("</think>")
            if end != -1:
                stripped = stripped[end + len("</think>"):].strip()
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = {"_parse_error": True, "_raw": content}

    return parsed, elapsed, usage


def validate_extracted(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """엔티티 리스트에 없는 source/target 가진 관계 자동 제거."""
    if not isinstance(extracted, dict):
        return extracted
    if extracted.get("_parse_error"):
        return extracted

    entities = extracted.get("entities") or []
    relations = extracted.get("relations") or []
    entity_names = {e.get("name") for e in entities if isinstance(e, dict) and e.get("name")}

    valid_relations = []
    removed_relations = []
    for r in relations:
        if not isinstance(r, dict):
            continue
        src = r.get("source")
        tgt = r.get("target")
        if src in entity_names and tgt in entity_names:
            valid_relations.append(r)
        else:
            missing = []
            if src not in entity_names:
                missing.append(f"source='{src}'")
            if tgt not in entity_names:
                missing.append(f"target='{tgt}'")
            removed_relations.append({**r, "_reason": f"not in entities: {', '.join(missing)}"})

    return {
        "entities": entities,
        "relations": valid_relations,
        "_removed_relations": removed_relations,
    }


def _chunk_meta(chunk: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "chunk_id": chunk.get("chunk_id"),
        "chunk_index": chunk.get("chunk_index"),
        "original_filename": chunk.get("original_filename"),
        "text_length": len(chunk.get("text") or ""),
    }


def run(chunks_path: str, output_path: str, limit: int | None, resume: bool) -> None:
    if not os.path.exists(chunks_path):
        raise FileNotFoundError(f"청크 파일 없음: {chunks_path}")

    with open(chunks_path, encoding="utf-8") as f:
        chunks = json.load(f)
    total_available = len(chunks)

    existing_results: list = []
    if resume and os.path.exists(output_path):
        try:
            with open(output_path, encoding="utf-8") as f:
                existing_data = json.load(f)
            existing_results = existing_data.get("results", []) or []
            done_chunk_ids = {
                r.get("chunk_id") for r in existing_results if "error" not in r
            }
            before = len(chunks)
            chunks = [c for c in chunks if c.get("chunk_id") not in done_chunk_ids]
            print(f"이어하기: 기존 {len(existing_results)}개, "
                  f"{before - len(chunks)}개 스킵, {len(chunks)}개 남음\n")
        except Exception as e:
            print(f"경고: 기존 결과 로드 실패({e}), 처음부터.\n", file=sys.stderr)
            existing_results = []

    if limit is not None and limit > 0:
        chunks = chunks[:limit]

    print(f"Qwen3 엔티티 추출 시작")
    print(f"  모델: {OLLAMA_MODEL} @ {OLLAMA_URL}")
    print(f"  처리 대상: {len(chunks)}개 청크"
          + (f" / 전체 {total_available}개 중" if limit else ""))
    if existing_results:
        print(f"  누적 예정: {len(existing_results) + len(chunks)}개\n")
    else:
        print()

    results: list = []
    total_time = 0.0
    total_prompt_tokens = 0
    total_completion_tokens = 0

    for i, chunk in enumerate(chunks, 1):
        text = chunk.get("text") or ""
        filename = chunk.get("original_filename") or "?"
        chunk_idx = chunk.get("chunk_index")
        print(f"[{i}/{len(chunks)}] {filename} (chunk {chunk_idx}, {len(text)}자)")

        if not text.strip():
            print("  스킵: 텍스트 비어있음")
            results.append({**_chunk_meta(chunk), "error": "empty text"})
            continue

        try:
            extracted_raw, elapsed, usage = extract_one(chunk)
            total_time += elapsed
            total_prompt_tokens += usage.get("prompt_tokens", 0)
            total_completion_tokens += usage.get("completion_tokens", 0)

            extracted = validate_extracted(extracted_raw)
            parse_failed = extracted.get("_parse_error") is True
            ent_count = len(extracted.get("entities", []) or [])
            rel_count = len(extracted.get("relations", []) or [])
            removed = len(extracted.get("_removed_relations", []) or [])

            if parse_failed:
                status = "JSON 파싱 실패"
            else:
                status = f"엔티티 {ent_count}, 관계 {rel_count}"
                if removed:
                    status += f" (무효 관계 {removed}개 제거)"
            print(f"  → {elapsed:.1f}초 "
                  f"(in={usage.get('prompt_tokens', '?')}, "
                  f"out={usage.get('completion_tokens', '?')}), {status}")

            results.append({
                **_chunk_meta(chunk),
                "elapsed_seconds": round(elapsed, 2),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "extracted": extracted,
            })
        except Exception as e:
            print(f"  실패: {type(e).__name__}: {e}")
            results.append({**_chunk_meta(chunk), "error": str(e)})

    all_results = existing_results + results

    successful = sum(1 for r in all_results if "error" not in r)
    parse_errors = sum(
        1 for r in all_results
        if isinstance(r.get("extracted"), dict) and r["extracted"].get("_parse_error")
    )
    total_entities = sum(
        len((r.get("extracted") or {}).get("entities") or [])
        for r in all_results if "error" not in r
    )
    total_relations = sum(
        len((r.get("extracted") or {}).get("relations") or [])
        for r in all_results if "error" not in r
    )
    total_removed_relations = sum(
        len((r.get("extracted") or {}).get("_removed_relations") or [])
        for r in all_results if "error" not in r
    )
    avg_this_run = total_time / max(len(results), 1)

    print("\n" + "=" * 60)
    print(f"이번 실행: {total_time:.1f}초, 처리 {len(results)}개, 평균 {avg_this_run:.1f}초/청크")
    print(f"전체 성공 {successful}/{len(all_results)}개, 파싱 실패 {parse_errors}개")
    print(f"엔티티 총 {total_entities}, 유효 관계 {total_relations} (무효 {total_removed_relations} 제거)")
    print(f"이번 토큰: 입력 {total_prompt_tokens}, 출력 {total_completion_tokens}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "model": OLLAMA_MODEL,
                "endpoint": OLLAMA_URL,
                "total_chunks": len(all_results),
                "successful": successful,
                "parse_errors": parse_errors,
                "last_run_seconds": round(total_time, 2),
                "last_run_chunks": len(results),
                "last_run_avg_seconds_per_chunk": round(avg_this_run, 2),
                "last_run_prompt_tokens": total_prompt_tokens,
                "last_run_completion_tokens": total_completion_tokens,
                "total_entities": total_entities,
                "total_valid_relations": total_relations,
                "total_removed_relations": total_removed_relations,
            },
            "results": all_results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Qwen3-14B-Q8 엔티티·관계 추출 PoC")
    parser.add_argument(
        "--chunks", default=os.path.join(CHUNKS_DIR, "golden_40.json"))
    parser.add_argument(
        "--out", default=os.path.join(GRAPHS_DIR, "qwen3", "extracted_40.json"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true",
                        help="기존 결과에서 이미 처리된 chunk_id 스킵하고 이어서")
    args = parser.parse_args()

    try:
        run(args.chunks, args.out, args.limit, args.resume)
        return 0
    except Exception as e:
        print(f"\n실패: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
