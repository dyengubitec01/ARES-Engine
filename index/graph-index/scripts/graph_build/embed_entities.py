# -*- coding: utf-8 -*-
"""그래프 엔티티 벡터 → Qdrant (increment 2a).

active 빌드의 엔티티 이름을 BGE-M3(청크와 동일 모델)로 임베딩해
Qdrant 컬렉션(dev: rag_graph_entities_v1_dev)에 적재하고,
rag_graph_entities.qdrant_point_id 를 채운다. (point_id = entity uuid)

용도: 질의 시점 엔티티 링킹 — 이름 문자열매칭 실패 시 cosine 폴백.
운영 청크 컬렉션(rag_chunks_v1)은 건드리지 않음. 새 컬렉션만 생성.

실행:
  .venv/Scripts/python.exe scripts/graph_build/embed_entities.py --db dev
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
# 한글 로그 깨짐 방지. reconfigure 사용(stdout 재할당 금지 — 원본 버퍼 GC 닫힘 방지)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import numpy as np  # noqa: E402
from sqlalchemy import text  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.models import (  # noqa: E402
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue, FilterSelector,
)

from config import settings  # noqa: E402
from embeddings.bge_m3_client import BGEM3Client  # noqa: E402
import build_graph as B  # noqa: E402

COLLECTION = {"dev": "rag_graph_entities_v1_dev", "prod": "rag_graph_entities_v1"}


def _vec(v):
    """Qdrant 전송형(list[float])으로. 재사용 벡터는 float32 ndarray, 신규 임베딩은 이미 list.

    정밀도(2026-08-03 prod 22.3만 벡터 실측): 컬렉션 저장형이 float32이므로(datatype
    미지정=기본 float32. 근거: 정규화 저장인데 벡터 노름이 1.00000002로 정확히 1이 아님)
    float32로 접는 것은 '저장된 값을 되찾는' 연산이다. API가 JSON 짧은 십진수를 주기에
    파싱된 float64는 저장 float32와 최대 4.3e-09 어긋나지만, 원본 대비 코사인유사도가
    1-2.2e-16(float64 머신 epsilon)이라 검색 순위에 영향이 없다.
    """
    return v.tolist() if isinstance(v, np.ndarray) else v


def main():
    ap = argparse.ArgumentParser(description="그래프 엔티티 벡터 → Qdrant")
    ap.add_argument("--db", default="dev", help="dev | prod")
    ap.add_argument("--upsert-batch", type=int, default=256)
    args = ap.parse_args()

    eng, db, schema = B.make_engine(args.db)
    coll = COLLECTION[args.db]
    print(f"[대상] db={db} schema={schema} | Qdrant collection={coll}")

    # 1. active 빌드 엔티티 로드
    with eng.connect() as c:
        bid = c.execute(text("SELECT id FROM rag_graph_builds WHERE status='active' ORDER BY id DESC LIMIT 1")).scalar()
        rows = c.execute(text(
            "SELECT id, name, entity_type, normalized_name FROM rag_graph_entities "
            "WHERE build_id=:b ORDER BY id"), {"b": bid}).fetchall()
    if not rows:
        raise SystemExit(f"active 빌드({bid}) 엔티티 없음")
    ents = [{"id": str(r[0]), "name": r[1], "type": r[2], "norm": r[3]} for r in rows]
    print(f"[1] active build_id={bid} 엔티티 {len(ents)}개")

    # 2. 임베딩 — 기존 Qdrant 벡터를 '이름 캐시'로 재사용, 새 이름만 BGE-M3.
    #    임베딩은 name(표면형)에만 의존 → 이름 안 바뀌면 벡터 동일. 이름이 거의 안 바뀌므로
    #    매 빌드 22.5만 전량 재임베딩(~50분)을 '새 이름 몇 개'로 축소. (별도 캐시테이블 없이 Qdrant가 캐시)
    qc = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, timeout=120)
    existing = [c.name for c in qc.get_collections().collections]
    print("[2] 임베딩 (기존 벡터 캐시 재사용, 새 이름만 BGE-M3)...")
    t0 = time.time()
    current_names = {e["name"] for e in ents}
    name_to_vec = {}                                    # 이전 빌드 {name: vector} (현재 쓰는 이름만 보관)
    if coll in existing:
        offset = None
        while True:
            pts, offset = qc.scroll(coll, limit=10000, with_vectors=True,
                                    with_payload=["name"], offset=offset)
            for p in pts:
                nm = (p.payload or {}).get("name")
                if nm in current_names and nm not in name_to_vec:
                    # float32 ndarray로 보관. 파이썬 list[float]로 들면 벡터당 52KB →
                    # 22.3만개 = 10.8GiB(호스트 90% 스파이크의 정체). ndarray는 4KB = 0.87GiB.
                    name_to_vec[nm] = np.asarray(p.vector, dtype=np.float32)
            if offset is None:
                break
    uniq_new = list(dict.fromkeys(e["name"] for e in ents if e["name"] not in name_to_vec))
    new_map = dict(zip(uniq_new, BGEM3Client().embed_texts(uniq_new))) if uniq_new else {}
    # 전량 vecs 리스트는 만들지 않는다(업서트에서 배치단위로 조회). 누락은 여기서 크게 실패.
    missing = [e["name"] for e in ents
               if e["name"] not in name_to_vec and e["name"] not in new_map]
    if missing:
        raise SystemExit(f"임베딩 누락 {len(missing)}건 (예: {missing[:3]})")
    first = ents[0]["name"]
    dim = len(name_to_vec[first] if first in name_to_vec else new_map[first])
    reused = sum(1 for e in ents if e["name"] in name_to_vec)
    print(f"    → 재사용 {reused} / 신규임베딩 {len(uniq_new)} / 전체 {len(ents)}, dim={dim}, {time.time()-t0:.0f}s")

    # 3. Qdrant 컬렉션 ensure (없으면 생성)
    if coll not in existing:
        qc.create_collection(coll, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
        print(f"[3] 컬렉션 생성: {coll} (dim={dim}, cosine)")
    else:
        print(f"[3] 컬렉션 존재: {coll} (기존 사용)")
    # build_id 페이로드 인덱스 (이전 빌드 벡터 GC용 필터 삭제에 사용). 이미 있으면 무시.
    try:
        qc.create_payload_index(coll, field_name="build_id", field_schema="integer")
    except Exception:
        pass

    # 4. 업서트 (point_id = entity uuid)
    #    PointStruct를 전량 만들지 않는다: pydantic이 vector를 list[float]로 되돌리므로
    #    22.3만개를 한 번에 만들면 float32 절감이 그대로 사라진다. 배치마다 생성·전송·폐기.
    n_up = 0
    for i in range(0, len(ents), args.upsert_batch):
        batch = ents[i:i + args.upsert_batch]
        pts_batch = [
            PointStruct(
                id=e["id"],
                vector=_vec(name_to_vec[e["name"]] if e["name"] in name_to_vec
                            else new_map[e["name"]]),
                payload={"entity_id": e["id"], "build_id": bid,
                         "name": e["name"], "entity_type": e["type"],
                         "normalized_name": e["norm"]})
            for e in batch
        ]
        qc.upsert(collection_name=coll, points=pts_batch)
        n_up += len(pts_batch)
    print(f"[4] 업서트 완료: {n_up} 포인트 (build_id={bid})")

    # 4.5 이전 빌드 벡터 GC — build_id != 현재 인 포인트 전부 삭제.
    #     업서트를 먼저 했으므로 빈 구간 없음(old→old+new→new only). 매 빌드 누적 방지.
    qc.delete(
        collection_name=coll,
        points_selector=FilterSelector(filter=Filter(
            must_not=[FieldCondition(key="build_id", match=MatchValue(value=bid))]
        )),
        wait=True,
    )
    print(f"[4.5] 이전 빌드 벡터 정리 완료 (build_id != {bid} 삭제)")

    # 5. qdrant_point_id 채움 (= entity uuid)
    with eng.begin() as c:
        c.execute(text("UPDATE rag_graph_entities SET qdrant_point_id = id::text WHERE build_id=:b"), {"b": bid})
    info = qc.get_collection(coll)
    print(f"[5] qdrant_point_id 갱신 완료. 컬렉션 포인트수={info.points_count} (=현재 빌드 엔티티수여야 정상)")
    print("[완료]")


if __name__ == "__main__":
    main()
