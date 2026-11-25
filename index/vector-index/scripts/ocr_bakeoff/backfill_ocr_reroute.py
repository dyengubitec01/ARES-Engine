"""깨진 텍스트레이어 PDF backfill 트리거 (OCR 라우팅 수정 배포 후 실행).

scope_scan.json의 영향 PDF들을 ER 서버 /re-embedding-requests 로 재투입한다
(embedding_mode=re_chunk, enable_ocr=true). 배포된 워커가 수정된 extractors.py로
깨진 페이지를 OCR 폴백 처리 → 청크 재생성/재임베딩.

⚠️ 전제: 코드 커밋 + 워커 이미지 재빌드·재배포가 **먼저** 끝나야 의미 있음.
   (옛 워커면 그대로 쓰레기 재생성)

기본 DRY-RUN. 실제 전송은 --apply. 세종 1건만: --only-sejong.

실행 예:
    # 무엇이 전송될지 미리보기 (전송 안 함)
    ./.venv/Scripts/python.exe scripts/ocr_bakeoff/backfill_ocr_reroute.py --only-sejong
    # 세종 1건 실제 전송 + 완료까지 모니터 + before/after 재스코어
    ./.venv/Scripts/python.exe scripts/ocr_bakeoff/backfill_ocr_reroute.py --only-sejong --apply --wait
    # 전체 46개 PDF
    ./.venv/Scripts/python.exe scripts/ocr_bakeoff/backfill_ocr_reroute.py --apply --wait
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests  # noqa: E402

from chunking.quality_score import analyze_document_consistency, score_chunk_corruption  # noqa: E402
from db.connection import get_db_session  # noqa: E402
from models.rdb_models import RagChunk, RagEmbeddingJob  # noqa: E402


def _profile_for(session, doc_id: str) -> str:
    """문서의 현재 임베딩 버전 → 프로필(하이브리드 보존)."""
    row = (session.query(RagChunk.embedding_version)
           .filter(RagChunk.doc_content_id == doc_id).first())
    ev = (row[0] if row else "") or ""
    return "bge_m3_hybrid_v2" if "hybrid" in ev else "bge_m3_v1"


def _corrupt_count(session, doc_id: str, gate: int) -> tuple[int, int]:
    """문서의 (깨짐 청크 수, 전체 청크 수) 재계산."""
    rows = (session.query(RagChunk.text)
            .filter(RagChunk.doc_content_id == doc_id).all())
    texts = [r[0] for r in rows if r[0] and len(r[0]) >= 20]
    if not texts:
        return 0, 0
    ctx = analyze_document_consistency(texts)
    bad = sum(1 for t in texts if score_chunk_corruption(t, doc_context=ctx).score >= gate)
    return bad, len(texts)


def _latest_job_status(session, doc_id: str):
    job = (session.query(RagEmbeddingJob)
           .filter(RagEmbeddingJob.doc_content_id == doc_id)
           .order_by(RagEmbeddingJob.enqueued_at.desc()).first())
    return (str(job.status), str(job.id)) if job else (None, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--er-url", default=os.environ.get("ER_BASE_URL", "http://localhost:8100"))
    ap.add_argument("--scope", default=str(Path(__file__).parent / "out" / "scope_scan.json"))
    ap.add_argument("--only-sejong", action="store_true", help="깨짐 청크 1위(세종) 1건만")
    ap.add_argument("--skip", type=int, default=0, help="상위 N개 건너뛰기(이미 처리한 것 제외)")
    ap.add_argument("--limit", type=int, default=0, help="상위 N개 PDF만 (0=전체)")
    ap.add_argument("--gate", type=int, default=6)
    ap.add_argument("--requested-by", default="ocr-textlayer-backfill-2026-07")
    ap.add_argument("--force", action="store_true", help="진행중 작업 무시하고 강제")
    ap.add_argument("--apply", action="store_true", help="실제 전송 (없으면 DRY-RUN)")
    ap.add_argument("--wait", action="store_true", help="완료까지 DB 폴링 + before/after 재스코어")
    ap.add_argument("--timeout", type=int, default=1800, help="문서당 완료 대기 최대초")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    scope = json.loads(Path(args.scope).read_text(encoding="utf-8"))
    pdfs = [d for d in scope if (d.get("filename") or "").lower().endswith(".pdf")]
    pdfs.sort(key=lambda d: d["corrupt_chunks"], reverse=True)  # 세종이 1위
    if args.only_sejong:
        pdfs = pdfs[:1]
    else:
        if args.skip:
            pdfs = pdfs[args.skip:]
        if args.limit:
            pdfs = pdfs[: args.limit]

    print(f"ER: {args.er_url}   대상 PDF: {len(pdfs)}개   "
          f"{'*** APPLY ***' if args.apply else 'DRY-RUN(전송안함)'}")
    print("-" * 78)

    if args.apply:
        try:
            requests.get(f"{args.er_url}/openapi.json", timeout=10).raise_for_status()
        except Exception as e:
            print(f"❌ ER 서버 접속 불가: {e}\n   --er-url 확인 (예: ER_BASE_URL 환경변수)")
            sys.exit(1)

    results = []
    with get_db_session() as session:
        for d in pdfs:
            doc_id = d["doc_content_id"]
            profile = _profile_for(session, doc_id)
            fn = (d.get("filename") or "")[:50]
            payload = {
                "doc_content_id": doc_id,
                "embedding_profile": profile,
                "embedding_mode": "re_chunk",
                "enable_ocr": True,
                "requested_by": args.requested_by,
                "force": args.force,
            }
            print(f"\n[{fn}]  깨짐 {d['corrupt_chunks']}/{d['total_chunks']}  profile={profile}")
            if not args.apply:
                print(f"  DRY-RUN payload: {json.dumps(payload, ensure_ascii=False)}")
                results.append({**d, "profile": profile, "submitted": False})
                continue

            before, _ = _corrupt_count(session, doc_id, args.gate)
            try:
                r = requests.post(f"{args.er_url}/re-embedding-requests", json=payload, timeout=30)
                r.raise_for_status()
                job_id = r.json().get("job_id")
                print(f"  ✅ 전송 job_id={job_id}")
            except Exception as e:
                print(f"  ❌ 전송 실패: {e}")
                results.append({**d, "profile": profile, "submitted": False, "error": str(e)})
                continue

            rec = {**d, "profile": profile, "submitted": True, "job_id": job_id, "before": before}
            if args.wait:
                deadline = time.time() + args.timeout
                status = None
                while time.time() < deadline:
                    time.sleep(5)
                    session.expire_all()
                    status, _ = _latest_job_status(session, doc_id)
                    if status in ("done", "failed"):
                        break
                    print(f"    ... status={status}", end="\r", flush=True)
                after, total = _corrupt_count(session, doc_id, args.gate)
                rec.update(status=status, after=after, total_now=total)
                mark = "✓" if (status == "done" and after < before) else "⚠"
                print(f"  {mark} status={status}  깨짐 {before} → {after} (/{total})")
            results.append(rec)

    out = Path(args.scope).parent / "backfill_result.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {out}")
    if not args.apply:
        print("실제 전송: --apply (세종만: --only-sejong --apply --wait)")


if __name__ == "__main__":
    main()
