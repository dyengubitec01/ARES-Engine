# -*- coding: utf-8 -*-
"""
Parent ID 백필 (확정 방식 = 임베딩 인접 grouping / emb_adj).
메모리: parent_chunking_decision_2026-06-12

원리
  각 청크 임베딩(이미 검색용으로 Qdrant에 있음)의 '인접 청크 코사인 유사도'를 보고,
  유사도 낮은 지점(하위 percentile)에서만 끊어 연속 청크를 parent로 묶는다.
  - LLM 0콜, MinIO 재추출 0, 재벡터화 0. 기존 벡터 재활용.
  - 연속(10/11) 보존(break 0~16%), 모든 포맷 일관, 근접중복은 안전하게 over-merge.

흐름 (문서별)
  Qdrant에서 청크 벡터+chunk_index 읽기  +  RDB에서 청크 텍스트 길이 읽기
  → 인접 코사인 → emb_adj grouping → parent_id
  → Qdrant payload + RDB chunk.metadata 에 parent_id 패치 (벡터 불변)

안전장치: DRY_RUN 기본(--apply 없으면), 체크포인트(parent_version) 멱등·재개, 문서별 try/except.

실행
  python scripts/parent_backfill/backfill_parents.py --doc-id <UUID> --dry-run
  python scripts/parent_backfill/backfill_parents.py --limit 10 --apply
  python scripts/parent_backfill/backfill_parents.py --apply              # 전체(주말)
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import OperationalError, DBAPIError
from sqlalchemy.orm.attributes import flag_modified
from qdrant_client.models import Filter, FieldCondition, MatchValue

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config import settings
from db.connection import database_url
from db.repositories import ChunkRepository
from models.rdb_models import DocDocumentContent, RagChunk
from models.enums import DocumentStatus
from storage.qdrant_client import QdrantClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# 백필 전용 엔진: 공용(prod 워커) 엔진과 분리. 사내망 VPN이 흔들리면 풀에 남은 커넥션의
# TCP가 half-open이 되어 pre_ping SELECT 1 이 죽은 소켓에서 무한 대기(hang)하는 문제 →
#  - NullPool: 커넥션 재사용 안 함(매 세션 새 연결) → 죽은 소켓 재사용 자체를 제거
#  - connect_timeout: 연결이 안 되면 10초 내 예외(무한대기 대신) → 아래 재시도 로직이 처리
#  - keepalives: 진행 중 연결도 TCP 레벨에서 죽음 감지
_engine = create_engine(
    database_url,
    poolclass=NullPool,
    connect_args={
        # 서버측 타임아웃(근본 방어): client가 죽어도 서버가 스스로 정리.
        #  - statement_timeout: 쿼리/락 대기가 이 시간 넘으면 서버가 취소→예외(→아래 재시도 처리). hang 방지.
        #  - idle_in_transaction_session_timeout: 강제종료된 client가 남긴 'idle in transaction'
        #    고아 백엔드를 서버가 자동 종료→락 해제(락 pileup 재발 방지).
        "options": (
            f"-csearch_path={settings.postgres_schema},public"
            " -c statement_timeout=45000"
            " -c idle_in_transaction_session_timeout=30000"
        ),
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    },
)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@contextmanager
def get_db_session():
    """백필 전용 세션(강화 엔진). 공용 get_db_session 과 동일 인터페이스."""
    session = _Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
logger = logging.getLogger("parent_backfill")

PARENT_VERSION = 1
PERCENTILE = 20      # 인접 유사도 하위 이 percentile 미만에서만 끊음 (낮을수록 coarse)
MIN_CHARS = 1500     # parent 최소 크기 (이만큼 차기 전엔 안 끊음)
MAX_CHARS = 5000     # parent 최대 크기 (넘으면 강제로 끊음)
CHECKPOINT = os.getenv("PARENT_CKPT", str(Path(__file__).with_name("checkpoint.json")))
TARGET_STATUS = DocumentStatus.COMPLETED.value
SCROLL_BATCH = 256
RETRY_BACKOFF = [2, 5, 15, 30]  # 커넥션/DNS 블립 재시도 대기(초). 사내망 VPN DNS는 간헐 실패(split-horizon)라 잠깐 뒤 재시도하면 대부분 통과.


def _cos(a: List[float], b: List[float]) -> float:
    d = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return d / (na * nb + 1e-9)


# ---------- Qdrant: 청크 벡터 + point ID 읽기 ----------
def read_chunk_vectors(
    qc: QdrantClient, doc_id: str
) -> Tuple[Dict[int, List[float]], Dict[int, object]]:
    """doc_content_id의 모든 포인트 → ({chunk_index: dense_vector}, {chunk_index: point_id}).

    point_id를 함께 반환해 패치 시 필터 재검색 없이 ID로 직접 batch set_payload 한다.
    """
    vecs: Dict[int, List[float]] = {}
    ids: Dict[int, object] = {}
    offset = None
    flt = Filter(must=[FieldCondition(key="doc_content_id", match=MatchValue(value=doc_id))])
    while True:
        points, offset = qc.client.scroll(
            collection_name=qc.collection_name,
            scroll_filter=flt,
            with_vectors=True,
            with_payload=["chunk_index"],
            limit=SCROLL_BATCH,
            offset=offset,
        )
        for p in points:
            ci = (p.payload or {}).get("chunk_index")
            if ci is None:
                continue
            vec = p.vector
            if isinstance(vec, dict):  # 하이브리드 named vector
                vec = vec.get("dense") or next(iter(vec.values()))
            if vec:
                vecs[int(ci)] = list(vec)
                ids[int(ci)] = p.id
        if offset is None:
            break
    return vecs, ids


# ---------- emb_adj grouping ----------
def emb_adj(order: List[int], vecs: Dict[int, List[float]], lens: Dict[int, int]) -> Dict[int, int]:
    """chunk_index 순서 리스트 → {chunk_index: parent_id}."""
    if len(order) <= 1:
        return {ci: 0 for ci in order}
    sims = [_cos(vecs[order[i]], vecs[order[i + 1]]) for i in range(len(order) - 1)]
    thr = statistics.quantiles(sims, n=100)[PERCENTILE - 1] if len(sims) > 10 else min(sims)

    parent: Dict[int, int] = {}
    pid = 0
    acc = lens.get(order[0], 0)
    parent[order[0]] = 0
    for i in range(len(order) - 1):
        nxt = order[i + 1]
        nlen = lens.get(nxt, 0)
        brk = (sims[i] < thr and acc >= MIN_CHARS) or (acc + nlen > MAX_CHARS)
        if brk:
            pid += 1
            acc = nlen
        else:
            acc += nlen
        parent[nxt] = pid
    return parent


# ---------- parent 내 위치 플래그 ----------
def build_chunk_info(order: List[int], parent: Dict[int, int]) -> Dict[int, dict]:
    """chunk_index 순서 + parent → {chunk_index: {parent_id, is_first, is_last}}.

    워커와 동일 기준: parent_id 가 직전/직후와 다르면 그 parent의 첫/마지막 청크.
    검색측 edge-detection(첫/마지막이면 인접 parent 회수)용.
    """
    n = len(order)
    info: Dict[int, dict] = {}
    for i, ci in enumerate(order):
        is_first = (i == 0) or (parent[order[i]] != parent[order[i - 1]])
        is_last = (i == n - 1) or (parent[order[i]] != parent[order[i + 1]])
        info[ci] = {"parent_id": parent[ci], "is_first": bool(is_first), "is_last": bool(is_last)}
    return info


# ---------- 패치 ----------
def patch_qdrant(qc: QdrantClient, doc_id: str, idx_info: Dict[int, dict],
                 ids: Dict[int, object]) -> int:
    """청크별 개별 호출 대신, 동일 payload 값끼리 point ID를 묶어 batch set_payload.

    같은 (parent_id, is_first, is_last) 조합 청크들을 한 번의 set_payload로 처리 →
    문서당 콜 수가 '청크 수' → 'payload 조합 수'(보통 5~10)로 줄어 수십 배 빠름.
    필터 재검색 없이 scroll에서 읽은 point ID를 직접 지정한다.
    """
    groups: Dict[Tuple[int, bool, bool], List[object]] = {}
    n = 0
    for cidx, inf in idx_info.items():
        pid = ids.get(cidx)
        if pid is None:  # Qdrant에 없는 청크(정합 안 맞음)는 스킵
            continue
        key = (inf["parent_id"], inf["is_first"], inf["is_last"])
        groups.setdefault(key, []).append(pid)
        n += 1

    keys = list(groups.keys())
    for gi, key in enumerate(keys):
        parent_id, is_first, is_last = key
        # 마지막 그룹만 wait=True로 문서당 1회 동기화 (나머지는 비동기 발사)
        qc.client.set_payload(
            collection_name=qc.collection_name,
            payload={
                "parent_id": parent_id,
                "parent_version": PARENT_VERSION,
                "is_first_in_parent": is_first,
                "is_last_in_parent": is_last,
            },
            points=groups[key],
            wait=(gi == len(keys) - 1),
        )
    return n


def patch_rdb(session, doc_uuid: UUID, idx_info: Dict[int, dict]) -> int:
    n = 0
    for row in ChunkRepository.get_by_doc_content(session, doc_uuid):
        inf = idx_info.get(row.chunk_index)
        if inf is None:
            continue
        md = dict(row.metadata_json or {})
        md["parent_id"] = inf["parent_id"]
        md["parent_version"] = PARENT_VERSION
        md["is_first_in_parent"] = inf["is_first"]
        md["is_last_in_parent"] = inf["is_last"]
        row.metadata_json = md
        flag_modified(row, "metadata_json")
        n += 1
    return n


# ---------- 문서 1건 ----------
def process_doc(doc_uuid: UUID, qc: QdrantClient, dry_run: bool) -> str:
    doc_id = str(doc_uuid)
    with get_db_session() as session:
        rows = ChunkRepository.get_by_doc_content(session, doc_uuid)
        lens = {r.chunk_index: len(r.text or "") for r in rows}
    if not lens:
        return "skip:no_chunks_rdb"

    vecs, ids = read_chunk_vectors(qc, doc_id)
    if not vecs:
        return "skip:no_vectors_qdrant"

    # chunk_index 교집합(둘 다 있는 것만), 순서대로
    order = sorted(set(lens) & set(vecs))
    if not order:
        return "skip:no_overlap"
    if len(order) < len(lens) * 0.9:
        logger.warning("  벡터 누락 많음: rdb=%d qdrant=%d overlap=%d", len(lens), len(vecs), len(order))

    idx_parent = emb_adj(order, vecs, lens)
    idx_info = build_chunk_info(order, idx_parent)
    n_parents = len(set(idx_parent.values()))
    logger.info("  청크 %d → parent %d", len(order), n_parents)

    if dry_run:
        return f"ok(dry):chunks={len(order)},parents={n_parents}"

    nq = patch_qdrant(qc, doc_id, idx_info, ids)
    with get_db_session() as session:
        nr = patch_rdb(session, doc_uuid, idx_info)
    logger.info("  패치: qdrant=%d rdb=%d", nq, nr)
    return f"ok:chunks={len(order)},parents={n_parents}"


# ---------- 목록/체크포인트 ----------
def list_target_docs() -> List[UUID]:
    with get_db_session() as session:
        rows = (
            session.query(DocDocumentContent.id)
            .filter(DocDocumentContent.status == TARGET_STATUS)
            .order_by(DocDocumentContent.id).all()
        )
    return [r[0] for r in rows]


def load_ckpt() -> Dict[str, int]:
    try:
        return json.load(open(CHECKPOINT, encoding="utf-8"))
    except Exception:
        return {}


def save_ckpt(ck):
    tmp = CHECKPOINT + ".tmp"
    json.dump(ck, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, CHECKPOINT)


def main():
    ap = argparse.ArgumentParser(description="Parent ID 백필 (임베딩 인접 grouping)")
    ap.add_argument("--doc-id")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--apply", action="store_true", help="실제 적용 (없으면 dry-run)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reprocess", action="store_true", help="체크포인트 무시 재처리")
    args = ap.parse_args()

    dry_run = not args.apply or args.dry_run
    logger.info("=== parent 백필(emb_adj) 시작 (DRY_RUN=%s, version=%d, p%d) ===",
                dry_run, PARENT_VERSION, PERCENTILE)

    qc, ck = QdrantClient(), load_ckpt()

    if args.doc_id:
        targets = [UUID(args.doc_id)]
    else:
        targets = [d for d in list_target_docs()
                   if args.reprocess or ck.get(str(d), 0) < PARENT_VERSION]
        if args.limit:
            targets = targets[:args.limit]

    logger.info("대상 문서 %d건", len(targets))
    stats = {"ok": 0, "skip": 0, "fail": 0}
    for i, doc_uuid in enumerate(targets, 1):
        logger.info("[%d/%d] doc=%s", i, len(targets), doc_uuid)
        result = None
        for attempt in range(len(RETRY_BACKOFF) + 1):
            try:
                result = process_doc(doc_uuid, qc, dry_run)
                break
            except (OperationalError, DBAPIError) as e:
                # 커넥션/DNS 계열: 재시도. 마지막 시도까지 실패하면 fail로 떨굼(체크포인트 미기록→다음 실행 시 재개).
                if attempt < len(RETRY_BACKOFF):
                    wait = RETRY_BACKOFF[attempt]
                    logger.warning("커넥션 오류(재시도 %d/%d, %ds 후): %s",
                                   attempt + 1, len(RETRY_BACKOFF), wait, e.__class__.__name__)
                    time.sleep(wait)
                    continue
                logger.exception("재시도 소진, 실패: %s", e)
                result = f"fail:{type(e).__name__}"
            except Exception as e:
                logger.exception("실패: %s", e)
                result = f"fail:{type(e).__name__}"
                break
        logger.info("  -> %s", result)
        kind = result.split(":")[0].split("(")[0]
        stats[kind] = stats.get(kind, 0) + 1
        if result.startswith("ok") and not dry_run:
            ck[str(doc_uuid)] = PARENT_VERSION
            save_ckpt(ck)

    logger.info("=== 완료: ok=%d skip=%d fail=%d ===",
                stats.get("ok", 0), stats.get("skip", 0), stats.get("fail", 0))


if __name__ == "__main__":
    main()
