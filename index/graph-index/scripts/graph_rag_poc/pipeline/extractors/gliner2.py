"""GLiNER2 (fastino/gliner2-multi-v1)로 청크에서 엔티티·관계 추출.

이전 extract_entities.py(Gemma), extract_entities_gliner.py(GLiNER-Relex)와
동일한 입출력 포맷을 유지해 1:1 비교 가능하도록 설계.

실행:
  .venv/Scripts/python.exe scripts/graph_rag_poc/extract_entities_gliner2.py
  .venv/Scripts/python.exe scripts/graph_rag_poc/extract_entities_gliner2.py --limit 5
"""
import argparse
import io
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
# graph_rag_poc/ 루트를 sys.path에 추가하여 pipeline.* 절대 import 가능하게
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from pipeline.shared.config import Config as C, CHUNKS_DIR, GRAPHS_DIR  # noqa: E402


MODEL_NAME = "fastino/gliner2-multi-v1"

ENTITY_LABELS: Dict[str, str] = {
    "organization": "company, institution, department, university, agency",
    "product": "specific product name, service name, solution name",
    "system": "software system, platform, framework",
    "technology": "technology term, algorithm, methodology, AI/ML technique",
    "project": "project name, initiative, business name",
    "person": "person name",
    "location": "place, region, country, city",
    "equipment": "hardware, sensor, device",
}

# GLiNER2 라벨 → Gemma 그래프와 호환되는 타입으로 매핑
LABEL_TO_TYPE: Dict[str, str] = {
    "organization": "ORG",
    "product": "PRODUCT",
    "system": "SYSTEM",
    "technology": "CONCEPT",
    "project": "PROJECT",
    "person": "PERSON",
    "location": "LOCATION",
    "equipment": "PRODUCT",
}

RELATION_SCHEMA: Dict[str, str] = {
    "leads": "organization that leads or chairs a project",
    "participates_in": "organization that participates in a specific project or task as a contributor",
    "develops": "organization that develops a product, system, or technology",
    "uses": "system or product that uses a technology",
    "includes": "system or product that contains a component",
    "responsible_for": "organization responsible for a specific task or deliverable",
}

# 한국어 끝 조사 정리
_TRAILING_JOSA = re.compile(
    r"(을|를|이|가|은|는|에|와|과|도|로|으로|에서|에게|으로서|에는|이라|라|만|까지|부터)\s*$"
)
_MAX_SPAN_CHARS = 50


def _clean_entity_text(text: str) -> str:
    cleaned = text.strip().rstrip(",.;:")
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = _TRAILING_JOSA.sub("", cleaned).strip()
    return cleaned


def _build_extracted(raw: Dict[str, Any]) -> Dict[str, Any]:
    """GLiNER2 결과를 Gemma 호환 스키마로 변환.

    raw: {'entities': {label: [text, ...]}, 'relation_extraction': {rel: [(h, t), ...]}}
    out: {'entities': [{name, type, description}], 'relations': [{source, target, type, description}]}
    """
    raw_entities = raw.get("entities") or {}
    raw_relations = raw.get("relation_extraction") or {}

    name_to_entity: Dict[str, Dict[str, Any]] = {}
    for label, texts in raw_entities.items():
        ent_type = LABEL_TO_TYPE.get(label, "OTHER")
        if not isinstance(texts, list):
            continue
        for t in texts:
            if not isinstance(t, str):
                continue
            if len(t) > _MAX_SPAN_CHARS:
                continue
            name = _clean_entity_text(t)
            if not name or len(name) <= 1:
                continue
            existing = name_to_entity.get(name)
            if existing is None:
                name_to_entity[name] = {
                    "name": name,
                    "type": ent_type,
                    "description": f"GLiNER2 label={label}",
                }

    entity_names = set(name_to_entity.keys())

    relations: List[Dict[str, Any]] = []
    seen_rel: set = set()
    for rel_type, pairs in raw_relations.items():
        if not isinstance(pairs, list):
            continue
        for pair in pairs:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            head_raw, tail_raw = pair
            if not isinstance(head_raw, str) or not isinstance(tail_raw, str):
                continue
            src = _clean_entity_text(head_raw)
            tgt = _clean_entity_text(tail_raw)
            if not src or not tgt or src == tgt:
                continue
            # 양쪽이 entity 리스트에 있을 때만 채택 (환각 방지)
            if src not in entity_names or tgt not in entity_names:
                continue
            key = (src, tgt, rel_type)
            if key in seen_rel:
                continue
            seen_rel.add(key)
            relations.append({
                "source": src,
                "target": tgt,
                "type": rel_type,
                "description": "GLiNER2",
            })

    return {
        "entities": list(name_to_entity.values()),
        "relations": relations,
    }


def extract_one(extractor, schema, chunk: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
    text = chunk.get("text") or ""
    t0 = time.time()
    raw = extractor.extract(text, schema)
    elapsed = time.time() - t0
    extracted = _build_extracted(raw)
    return extracted, elapsed


def _chunk_meta(chunk: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "chunk_id": chunk.get("chunk_id"),
        "chunk_index": chunk.get("chunk_index"),
        "original_filename": chunk.get("original_filename"),
        "text_length": len(chunk.get("text") or ""),
    }


def run(chunks_path: str, output_path: str, limit: int | None) -> None:
    if not os.path.exists(chunks_path):
        raise FileNotFoundError(f"청크 파일 없음: {chunks_path}")
    with open(chunks_path, encoding="utf-8") as f:
        chunks = json.load(f)
    total_available = len(chunks)
    if limit is not None and limit > 0:
        chunks = chunks[:limit]

    print(f"GLiNER2 엔티티 추출 시작")
    print(f"  모델: {MODEL_NAME}")
    print(f"  처리 대상: {len(chunks)}개 청크"
          + (f" / 전체 {total_available}개 중" if limit else ""))
    print(f"  엔티티 라벨: {len(ENTITY_LABELS)}, 관계 스키마: {len(RELATION_SCHEMA)}\n")

    print("모델 로드 중...")
    t0 = time.time()
    from gliner2 import GLiNER2
    extractor = GLiNER2.from_pretrained(MODEL_NAME)
    load_time = time.time() - t0
    print(f"  → 로드 완료: {load_time:.1f}초\n")

    # 스키마 한 번만 빌드 (재사용)
    schema = (
        extractor.create_schema()
        .entities(ENTITY_LABELS)
        .relations(RELATION_SCHEMA)
    )

    results: List[Dict[str, Any]] = []
    total_time = 0.0

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
            extracted, elapsed = extract_one(extractor, schema, chunk)
            total_time += elapsed
            ent_count = len(extracted.get("entities", []))
            rel_count = len(extracted.get("relations", []))
            print(f"  → {elapsed:.2f}초, 엔티티 {ent_count}, 관계 {rel_count}")
            results.append({
                **_chunk_meta(chunk),
                "elapsed_seconds": round(elapsed, 3),
                "extracted": extracted,
            })
        except Exception as e:
            print(f"  실패: {type(e).__name__}: {e}")
            results.append({**_chunk_meta(chunk), "error": str(e)})

    successful = sum(1 for r in results if "error" not in r)
    total_entities = sum(
        len((r.get("extracted") or {}).get("entities") or [])
        for r in results if "error" not in r
    )
    total_relations = sum(
        len((r.get("extracted") or {}).get("relations") or [])
        for r in results if "error" not in r
    )
    avg = total_time / max(len(results), 1)

    print("\n" + "=" * 60)
    print(f"실행 완료: {total_time:.1f}초, 평균 {avg:.2f}초/청크")
    print(f"모델 로드: {load_time:.1f}초")
    print(f"성공 {successful}/{len(results)}개")
    print(f"엔티티 총 {total_entities}, 관계 총 {total_relations}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "model": MODEL_NAME,
                "total_chunks": len(results),
                "successful": successful,
                "total_seconds": round(total_time, 2),
                "avg_seconds_per_chunk": round(avg, 3),
                "model_load_seconds": round(load_time, 2),
                "total_entities": total_entities,
                "total_relations": total_relations,
            },
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="GLiNER2 엔티티·관계 추출 PoC")
    parser.add_argument(
        "--chunks", default=os.path.join(CHUNKS_DIR, "golden_40.json"))
    parser.add_argument(
        "--out", default=os.path.join(GRAPHS_DIR, "gliner2", "extracted_40.json"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    try:
        run(args.chunks, args.out, args.limit)
        return 0
    except Exception as e:
        print(f"\n실패: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
