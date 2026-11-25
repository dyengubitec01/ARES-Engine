"""깨진 텍스트레이어 범위 스캔 (문서 단위 집계).

rag_chunks 전체를 문서(doc_content_id) 단위로 corruption 채점 → 게이트(기본 6)
이상 청크 비율로 "폰트 깨짐 영향 문서"를 랭킹. backfill 대상 규모 산정용.

실행:
    ./.venv/Scripts/python.exe scripts/ocr_bakeoff/scope_scan.py --gate 6
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from chunking.quality_score import (  # noqa: E402
    analyze_document_consistency,
    score_chunk_corruption,
)
from db.connection import get_db_session  # noqa: E402
from models.rdb_models import (  # noqa: E402
    DocDocument,
    DocDocumentContent,
    RagChunk,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", type=int, default=6, help="corruption 게이트(이상=깨짐)")
    ap.add_argument("--min-len", type=int, default=20)
    ap.add_argument("--out", type=str, default=str(Path(__file__).parent / "out"))
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    with get_db_session() as session:
        print("[1/2] rag_chunks 문서 단위 채점 중 ...")
        by_doc = defaultdict(list)
        total = 0
        for row in session.query(
            RagChunk.doc_content_id, RagChunk.text, RagChunk.page_start,
        ).yield_per(3000):
            total += 1
            if row.text and len(row.text) >= args.min_len:
                by_doc[str(row.doc_content_id)].append(row)

        docs = []
        corrupt_chunks_total = 0
        for doc_id, rows in by_doc.items():
            ctx = analyze_document_consistency([r.text for r in rows])
            n_corrupt = 0
            max_score = 0
            for r in rows:
                sc = score_chunk_corruption(r.text, doc_context=ctx).score
                if sc >= args.gate:
                    n_corrupt += 1
                max_score = max(max_score, sc)
            if n_corrupt == 0:
                continue
            corrupt_chunks_total += n_corrupt
            docs.append({
                "doc_content_id": doc_id,
                "total_chunks": len(rows),
                "corrupt_chunks": n_corrupt,
                "corrupt_ratio": round(n_corrupt / len(rows), 3),
                "max_score": max_score,
            })

        docs.sort(key=lambda d: d["corrupt_chunks"], reverse=True)

        print("[2/2] 영향 문서 제목 역추적 ...")
        for d in docs:
            content = session.query(DocDocumentContent).filter(
                DocDocumentContent.id == d["doc_content_id"]).first()
            d["filename"] = content.original_filename if content else None
            if content:
                doc = session.query(DocDocument).filter(
                    DocDocument.id == content.document_id).first()
                d["title"] = doc.title if doc else None

    # 요약
    print("\n" + "=" * 78)
    print(f"전체 청크: {total:,}")
    print(f"깨짐 청크(≥{args.gate}): {corrupt_chunks_total:,}")
    print(f"영향 문서 수: {len(docs)}")
    print("=" * 78)
    print(f"\n{'#':>2} {'깨짐/전체':>12} {'비율':>6} {'최고':>4}  파일명")
    for i, d in enumerate(docs, 1):
        fn = (d.get("filename") or d.get("title") or d["doc_content_id"])[:52]
        print(f"{i:>2} {str(d['corrupt_chunks'])+'/'+str(d['total_chunks']):>12} "
              f"{d['corrupt_ratio']:>6.1%} {d['max_score']:>4}  {fn}")

    out = Path(args.out) / "scope_scan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {out}")


if __name__ == "__main__":
    main()
