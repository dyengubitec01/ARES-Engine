"""나쁜 OCR 청크 finder (OCR 바이크오프 1단계).

rag_chunks 의 text 를 chunking.quality_score.score_chunk_corruption 으로 채점해
폰트 깨짐/인코딩 오류/의심 스크립트가 심한 "OCR 실패 의심" 청크를 랭킹한다.
각 후보를 원본 PDF + 페이지까지 역추적하고, --render 시 해당 페이지를 PNG로 렌더한다.

경로: rag_chunks.doc_content_id
      → rag_embedding_jobs(minio_bucket, minio_object_key)  [폴백: doc_documents.minio_url]
      → MinIO 원본 PDF → PyMuPDF 페이지 렌더 → PNG

실행 (Vector_RAG_Index 루트에서, .env 자동 로드):
    ./.venv/Scripts/python.exe scripts/ocr_bakeoff/find_bad_ocr_chunks.py --top 20
    ./.venv/Scripts/python.exe scripts/ocr_bakeoff/find_bad_ocr_chunks.py --top 10 --render --out scripts/ocr_bakeoff/pages

출력:
    - 콘솔 랭킹 표
    - <out>/candidates.json  (역추적 메타 포함)
    - --render 시 <out>/pageimg/<doc>_p<page>_<chunk>.png
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# Vector_RAG_Index 루트를 import 경로에 추가 (scripts/ocr_bakeoff/ 에서 실행 대비)
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from chunking.quality_score import (  # noqa: E402
    analyze_document_consistency,
    classify_score,
    score_chunk_corruption,
)
from db.connection import get_db_session  # noqa: E402
from models.rdb_models import (  # noqa: E402
    DocDocument,
    DocDocumentContent,
    RagChunk,
    StorageObjectFile,
)
from config import settings  # noqa: E402


def _fetch_scored(session, min_score: int, min_len: int, page_only: bool):
    """rag_chunks 전체를 문서 단위로 채점. score>=min_score 인 후보만 반환."""
    # 문서(doc_content_id) 단위로 묶어 doc_context(희귀 스크립트)까지 반영
    q = session.query(
        RagChunk.id,
        RagChunk.doc_content_id,
        RagChunk.chunk_index,
        RagChunk.text,
        RagChunk.page_start,
        RagChunk.page_end,
        RagChunk.token_count,
    )
    by_doc: dict = defaultdict(list)
    total = 0
    for row in q.yield_per(2000):
        total += 1
        if page_only and row.page_start is None:
            continue
        if not row.text or len(row.text) < min_len:
            continue
        by_doc[str(row.doc_content_id)].append(row)

    candidates = []
    for doc_id, rows in by_doc.items():
        doc_ctx = analyze_document_consistency([r.text for r in rows])
        for r in rows:
            res = score_chunk_corruption(r.text, doc_context=doc_ctx)
            if res.score < min_score:
                continue
            candidates.append({
                "chunk_id": str(r.id),
                "doc_content_id": doc_id,
                "chunk_index": r.chunk_index,
                "page_start": r.page_start,
                "page_end": r.page_end,
                "token_count": r.token_count,
                "score": res.score,
                "classification": classify_score(res.score),
                "signals": res.to_dict()["signals"],
                "suspicious_char_samples": res.suspicious_char_samples[:20],
                "text_snippet": r.text[:300],
                "text_len": len(r.text),
            })
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates, total


def _resolve_source(session, doc_content_id: str):
    """doc_content_id → (bucket, object_key, filename, title). 원본 PDF 위치.

    storage_object_files 에서 렌더 가능한 원본 파일을 고른다.
    우선순위: PDF content_type > kind(origin, raw) 순. 폴백: doc_documents.minio_url.
    """
    files = (
        session.query(StorageObjectFile)
        .filter(StorageObjectFile.doc_content_id == doc_content_id)
        .all()
    )

    def _rank(f):
        is_pdf = (f.content_type or "").lower().find("pdf") >= 0 \
            or (f.object_key or "").lower().endswith(".pdf")
        kind_pref = {"origin": 0, "raw": 1}.get(str(f.kind), 5)
        return (0 if is_pdf else 1, kind_pref)

    bucket = key = None
    if files:
        best = sorted(files, key=_rank)[0]
        bucket, key = best.bucket, best.object_key

    content = (
        session.query(DocDocumentContent)
        .filter(DocDocumentContent.id == doc_content_id)
        .first()
    )
    filename = content.original_filename if content else None
    title = None
    if content:
        doc = (
            session.query(DocDocument)
            .filter(DocDocument.id == content.document_id)
            .first()
        )
        if doc:
            title = doc.title
            if not key:  # 폴백
                key = doc.minio_url
    return {
        "minio_bucket": bucket or settings.minio_bucket,
        "minio_object_key": key,
        "original_filename": filename,
        "title": title,
    }


def _render_page(minio, bucket, key, page_no_1based, out_png, scale):
    """MinIO 원본 PDF에서 지정 페이지를 PNG로 렌더."""
    import fitz  # PyMuPDF

    data = minio.download_object(bucket, key)
    doc = fitz.open(stream=data, filetype="pdf")
    idx = max(0, (page_no_1based or 1) - 1)
    idx = min(idx, doc.page_count - 1)
    page = doc.load_page(idx)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out_png))
    doc.close()
    return idx + 1


def main():
    ap = argparse.ArgumentParser(description="나쁜 OCR 청크 finder")
    ap.add_argument("--top", type=int, default=20, help="상위 N개 후보")
    ap.add_argument("--min-score", type=int, default=3,
                    help="이 점수 이상만 후보 (3~5 약한의심, 6+ 강한의심)")
    ap.add_argument("--min-len", type=int, default=20, help="최소 텍스트 길이")
    ap.add_argument("--all-chunks", action="store_true",
                    help="page_start 없는 청크(스프레드시트 등)도 포함")
    ap.add_argument("--render", action="store_true",
                    help="상위 후보의 원본 페이지를 PNG로 렌더 (MinIO 접근)")
    ap.add_argument("--scale", type=float, default=settings.ocr_render_scale,
                    help="렌더 해상도 배율")
    ap.add_argument("--out", type=str,
                    default=str(Path(__file__).parent / "out"),
                    help="출력 디렉터리")
    args = ap.parse_args()

    # Windows 콘솔 한글 깨짐 방지
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with get_db_session() as session:
        print(f"[1/3] rag_chunks 채점 중 (min_score={args.min_score}) ...")
        candidates, total = _fetch_scored(
            session, args.min_score, args.min_len, page_only=not args.all_chunks
        )
        print(f"      전체 청크 {total}개 스캔 → 의심 후보 {len(candidates)}개")

        top = candidates[: args.top]
        print(f"[2/3] 상위 {len(top)}개 원본 역추적 중 ...")
        for c in top:
            c["source"] = _resolve_source(session, c["doc_content_id"])

        if args.render:
            from storage.minio_client import MinIOClient
            minio = MinIOClient()
            img_dir = out_dir / "pageimg"
            print(f"[3/3] 페이지 렌더 → {img_dir}")
            for c in top:
                key = c["source"]["minio_object_key"]
                if not key:
                    c["rendered_png"] = None
                    print(f"      - chunk {c['chunk_index']}: 원본 키 없음, 스킵")
                    continue
                png = img_dir / (
                    f"{c['doc_content_id'][:8]}_p{c['page_start']}_c{c['chunk_index']}.png"
                )
                try:
                    used = _render_page(
                        minio, c["source"]["minio_bucket"], key,
                        c["page_start"], png, args.scale,
                    )
                    c["rendered_png"] = str(png)
                    c["rendered_page"] = used
                    print(f"      - chunk {c['chunk_index']} (score {c['score']}) "
                          f"p{used} → {png.name}")
                except Exception as e:
                    c["rendered_png"] = None
                    c["render_error"] = str(e)
                    print(f"      - chunk {c['chunk_index']}: 렌더 실패 {e}")
        else:
            print("[3/3] 렌더 스킵 (--render 로 원본 페이지 이미지 추출)")

    # 콘솔 표
    print("\n=== OCR 실패 의심 청크 랭킹 ===")
    print(f"{'#':>2} {'score':>5} {'class':<16} {'page':>5} {'len':>5}  snippet")
    for i, c in enumerate(top, 1):
        snip = c["text_snippet"][:60].replace("\n", " ")
        print(f"{i:>2} {c['score']:>5} {c['classification']:<16} "
              f"{str(c['page_start']):>5} {c['text_len']:>5}  {snip}")

    out_json = out_dir / "candidates.json"
    out_json.write_text(
        json.dumps(top, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n저장: {out_json}")
    if not args.render:
        print("페이지 이미지가 필요하면: --render --out <dir>")


if __name__ == "__main__":
    main()
