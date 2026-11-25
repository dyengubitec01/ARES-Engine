"""backfill 제출 후 완료 폴링 + before/after 재스코어.

backfill_result.json(submitted 문서 + before)을 읽어, 각 문서의 최신 job이
done/failed 될 때까지 폴링하고, 끝나면 corruption을 재계산해 before→after 보고.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from chunking.quality_score import analyze_document_consistency, score_chunk_corruption  # noqa: E402
from db.connection import get_db_session  # noqa: E402
from models.rdb_models import RagChunk, RagEmbeddingJob  # noqa: E402

GATE = 6
POLL_SEC = 20
TIMEOUT_SEC = 5400  # 90분


def _status(session, doc_id):
    j = (session.query(RagEmbeddingJob)
         .filter(RagEmbeddingJob.doc_content_id == doc_id)
         .order_by(RagEmbeddingJob.enqueued_at.desc()).first())
    return str(j.status) if j else None


def _corrupt(session, doc_id):
    rows = session.query(RagChunk.text).filter(RagChunk.doc_content_id == doc_id).all()
    texts = [r[0] for r in rows if r[0] and len(r[0]) >= 20]
    if not texts:
        return 0, 0
    ctx = analyze_document_consistency(texts)
    bad = sum(1 for t in texts if score_chunk_corruption(t, doc_context=ctx).score >= GATE)
    return bad, len(texts)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    res = json.loads((Path(__file__).parent / "out" / "backfill_result.json").read_text(encoding="utf-8"))
    docs = [x for x in res if x.get("submitted")]
    ids = {x["doc_content_id"]: x for x in docs}
    print(f"모니터 시작: {len(ids)}개 문서 완료 대기 (gate={GATE})")

    deadline = time.time() + TIMEOUT_SEC
    while time.time() < deadline:
        time.sleep(POLL_SEC)
        with get_db_session() as s:
            s.expire_all()
            st = [_status(s, d) for d in ids]
        done = sum(1 for x in st if x == "done")
        failed = sum(1 for x in st if x == "failed")
        pending = len(st) - done - failed
        print(f"  진행: done={done} failed={failed} 처리중={pending}")
        if pending == 0:
            break

    print("\n=== before → after 재스코어 ===")
    tot_before = tot_after = 0
    rows_out = []
    with get_db_session() as s:
        for doc_id, x in ids.items():
            before = x.get("before", 0)
            after, total = _corrupt(s, doc_id)
            status = _status(s, doc_id)
            tot_before += before; tot_after += after
            fn = (x.get("filename") or doc_id)[:46]
            mark = "✓" if after == 0 else ("↓" if after < before else "⚠")
            print(f"  {mark} {before:>3}→{after:<3} [{status:<7}] {fn}")
            rows_out.append({"doc_content_id": doc_id, "filename": x.get("filename"),
                             "before": before, "after": after, "status": status, "total": total})
    print(f"\n총계: 깨짐 {tot_before} → {tot_after}  (문서 {len(ids)}개)")
    (Path(__file__).parent / "out" / "backfill_monitor.json").write_text(
        json.dumps(rows_out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
