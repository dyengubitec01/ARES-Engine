"""옛 graph build GC — active + 직전 N개(롤백용)만 남기고 오래된 superseded 빌드 삭제.

빌드는 매빌드 누적되므로(build_graph는 옛 active를 superseded 표시만 함) 주기적 정리 필요.
읽기 경로는 status='active'만 보므로 누적은 정확성 무해·저장공간 문제 → 이 스크립트로 정리.

자식부터 순서삭제(cascade 헛일 회피): edges → entity_chunks → entities → communities
→ doc_status → builds. 단일 트랜잭션(중간 실패 시 전부 롤백). active/building 은 절대 미삭제.

권한: raguser는 DML만 가능 → DELETE는 OK. VACUUM/ANALYZE 는 owner(admin) 필요라 미수행
(autovacuum 의존). 매빌드 재구축이라 일반 정리로 충분(VACUUM FULL 불필요).
FK 참조컬럼 인덱스(ix_gedge_source_entity/ix_gedge_target_entity/ix_gec_entity)가 있어야
엔티티 삭제 cascade가 빠름 — 없으면 풀스캔으로 폭사(admin이 1회 생성, schema_graph_prod.sql 참조).

실행:
  python scripts/graph_build/gc_old_builds.py --db prod                 # active + 직전 1개 보존
  python scripts/graph_build/gc_old_builds.py --db prod --keep-superseded 2
  python scripts/graph_build/gc_old_builds.py --db prod --dry-run       # 삭제 대상만 출력
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from urllib.parse import quote_plus

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import create_engine, text  # noqa: E402

from config import settings  # noqa: E402

# 자식부터 → 부모 순서 (cascade 중복작업 회피)
_DELETE_ORDER = [
    ("rag_graph_edges", "build_id"),
    ("rag_graph_entity_chunks", "build_id"),
    ("rag_graph_entities", "build_id"),
    ("rag_graph_communities", "build_id"),
    ("rag_graph_doc_status", "build_id"),
    ("rag_graph_builds", "id"),
]


def make_engine(target: str):
    if target == "dev":
        db, schema = "ragdb_dev", "rag_dev"
    elif target == "prod":
        db, schema = settings.postgres_db, settings.postgres_schema
    else:
        raise SystemExit(f"--db 는 dev|prod 만 허용 (입력: {target})")
    url = (
        f"postgresql://{settings.postgres_user}:{quote_plus(settings.postgres_password)}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{db}"
    )
    eng = create_engine(url, connect_args={"options": f"-csearch_path={schema},public"})
    return eng, db, schema


def main():
    ap = argparse.ArgumentParser(description="옛 graph build GC (active + 직전 N개만 보존)")
    ap.add_argument("--db", default="dev", help="dev | prod")
    ap.add_argument("--keep-superseded", type=int, default=1,
                    help="active 외에 보존할 직전 superseded 빌드 수(롤백용, 기본 1=어제 빌드만)")
    ap.add_argument("--dry-run", action="store_true", help="삭제 대상만 출력하고 실제 삭제 안 함")
    args = ap.parse_args()

    if args.keep_superseded < 0:
        raise SystemExit("--keep-superseded 는 0 이상이어야 합니다.")

    eng, db, schema = make_engine(args.db)
    print(f"[GC 대상] db={db} schema={schema} keep_superseded={args.keep_superseded}")

    with eng.connect() as c:
        active_ids = [r[0] for r in c.execute(
            text("SELECT id FROM rag_graph_builds WHERE status='active' ORDER BY id")).fetchall()]
        # 보존: active 전부 + 가장 최근 superseded N개. 삭제: 그 외 superseded.
        del_ids = [r[0] for r in c.execute(text(
            "SELECT id FROM rag_graph_builds WHERE status='superseded' "
            "AND id NOT IN (SELECT id FROM rag_graph_builds WHERE status='superseded' "
            "ORDER BY id DESC LIMIT :keep) ORDER BY id"
        ), {"keep": args.keep_superseded}).fetchall()]
        kept_superseded = [r[0] for r in c.execute(text(
            "SELECT id FROM rag_graph_builds WHERE status='superseded' "
            "ORDER BY id DESC LIMIT :keep"), {"keep": args.keep_superseded}).fetchall()]

    print(f"  active(보존)            : {active_ids}")
    print(f"  직전 superseded(보존)   : {sorted(kept_superseded)}")
    print(f"  삭제 대상 build_id       : {del_ids or '(없음)'}")

    # 안전장치: active 가 비었거나 삭제대상에 active/보존대상이 섞이면 중단
    if not active_ids:
        raise SystemExit("[중단] active 빌드가 없습니다 — GC 미수행(상태 이상).")
    forbidden = set(active_ids) | set(kept_superseded)
    if set(del_ids) & forbidden:
        raise SystemExit(f"[중단] 삭제대상에 active/보존빌드가 포함됨: {set(del_ids) & forbidden}")

    if not del_ids:
        print("[GC] 삭제할 옛 빌드 없음. 종료.")
        return

    if args.dry_run:
        with eng.connect() as c:
            print("[dry-run] 삭제 예정 행수:")
            for tbl, col in _DELETE_ORDER[:-1]:
                n = c.execute(text(f"SELECT count(*) FROM {tbl} WHERE {col} = ANY(:ids)"),
                              {"ids": del_ids}).scalar()
                print(f"    {tbl}: {n:,}")
        print("[dry-run] 실제 삭제 안 함.")
        return

    print("[GC] 삭제 시작 (단일 트랜잭션)...")
    t_all = time.time()
    with eng.begin() as conn:
        for tbl, col in _DELETE_ORDER:
            t0 = time.time()
            res = conn.execute(text(f"DELETE FROM {tbl} WHERE {col} = ANY(:ids)"), {"ids": del_ids})
            print(f"    {tbl}: {res.rowcount:,}행 삭제  ({time.time()-t0:.1f}s)", flush=True)
    print(f"[GC] 완료 — build {del_ids} 제거, 총 {time.time()-t_all:.1f}s")
    print("    (공간 회수/통계는 autovacuum 의존 — raguser는 VACUUM 권한 없음)")


if __name__ == "__main__":
    main()
