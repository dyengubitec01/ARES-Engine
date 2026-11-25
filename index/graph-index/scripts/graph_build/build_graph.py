"""그래프 백본 빌드 (increment 1: LLM 0, Qdrant 0) — 활성 청크 → 엔티티/엣지/커뮤니티 → RDB.

흐름:
  활성 청크 (rag_chunks ⨝ doc_document_content WHERE is_active='Y')
    → GLiNER2 엔티티 추출 (로컬 NER, LLM 0)
    → 이름 정규화 cross-doc 병합        → rag_graph_entities
    → 엔티티↔청크 라우팅 (실 chunk_id)   → rag_graph_entity_chunks
    → 공출현 엣지                        → rag_graph_edges
    → Louvain 커뮤니티                   → rag_graph_communities + entity.community_id
  버전드: rag_graph_builds 행(status=building→active), 이전 active는 superseded.

다음 increment(미포함): 관계 라벨/요약·커뮤니티 요약(LLM), 엔티티 벡터·Qdrant 컬렉션.

추출 라벨/정규화 로직은 PoC scripts/graph_rag_poc/pipeline/extractors/gliner2.py 재사용.

실행:
  .venv/Scripts/python.exe scripts/graph_build/build_graph.py --db dev
  .venv/Scripts/python.exe scripts/graph_build/build_graph.py --db dev --limit 200
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import uuid
from collections import Counter, defaultdict
from itertools import combinations
from urllib.parse import quote_plus

import requests

# 한글 로그 깨짐 방지. reconfigure 사용(stdout 재할당 금지) — 재할당하면 원본 버퍼가
# GC 때 닫혀, 이 모듈을 import 하는 쪽(embed_entities)에서 "I/O operation on closed file" 발생.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 프로젝트 루트 import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import networkx as nx  # noqa: E402
from networkx.algorithms.community import louvain_communities  # noqa: E402
from sqlalchemy import create_engine, text, bindparam  # noqa: E402

from config import settings  # noqa: E402
import graph_models as m  # noqa: E402  # 그래프 ORM(rag_graph_*). graph 레포 소유(=models/ 네임스페이스 분리, base는 models 통째 소유)


MODEL_NAME = "fastino/gliner2-multi-v1"

# GLiNER2 엔티티 라벨 (PoC gliner2.py와 동일)
ENTITY_LABELS = {
    "organization": "company, institution, department, university, agency",
    "product": "specific product name, service name, solution name",
    "system": "software system, platform, framework",
    "technology": "technology term, algorithm, methodology, AI/ML technique",
    "project": "project name, initiative, business name",
    "person": "person name",
    "location": "place, region, country, city",
    "equipment": "hardware, sensor, device",
}
LABEL_TO_TYPE = {
    "organization": "ORG", "product": "PRODUCT", "system": "SYSTEM",
    "technology": "CONCEPT", "project": "PROJECT", "person": "PERSON",
    "location": "LOCATION", "equipment": "PRODUCT",
}

_TRAILING_JOSA = re.compile(
    r"(을|를|이|가|은|는|의|에|와|과|도|로|으로|에서|에게|으로서|에는|이라|라|만|까지|부터)\s*$"
)
_WS = re.compile(r"\s+")
_MAX_SPAN_CHARS = 50

# ── 표 구조 라벨 스톱워드 (정규화형 = 공백제거+casefold) ──────────────────────
# 내역서·품셈 표의 머리글/꼬리글이 GLiNER2에 엔티티로 잡히는 것 제거. build42 실측 최악은
# '소계'(3,796청크 / degree 1,271) — 무관한 청크를 대량으로 붙이는 순수 노이즈 허브다.
#
# 중요: 도메인 용어는 절대 넣지 말 것. 보통인부·특별인부·재료비·노무비·경비·중기터파기·
# 통신외선공·굴삭기 등은 표에 자주 나오지만 표준품셈/내역서의 **정식 용어**이고 description도
# 정확하다(예: 경비="공구손료를 포함하며, 노무비의 3%로 산출"). 지우면 단가·산출기준 질의를
# 못 받는다. 여기 넣는 것은 "그 자체로 아무 대상을 가리키지 않는 표 구조어"뿐.
ENTITY_STOPWORDS = frozenset({
    # build42 에 실제 존재 확인된 것
    "소계", "산출근거", "합계", "총계", "비고", "단위", "수량", "규격",
    "적용", "구분", "기타", "공통",
    # 현재 빌드엔 없지만 동일 부류 — 표준품셈 문서가 적재되면 나타날 수 있어 선반영
    "품명", "금액", "호표", "세부내역", "내역", "산출", "명칭", "일위대가",
})

# 순수 숫자(구분자 허용) 엔티티 = 표에서 뽑힌 금액·수량. build42 에 3,035개.
# 주의: '숫자로 시작'으로 넓히면 안 된다 — 5G / 4차 산업혁명 / 600V 비닐절연 전선 /
# 50ton 트럭 크레인 / 1PE(Φ36) 같은 정상 엔티티가 6,447개나 걸린다.
_NUMERIC_ONLY = re.compile(r"^[0-9][0-9.,\-/]*$")


def is_junk_entity(norm: str) -> bool:
    """표 구조 라벨 / 순수 숫자 = 그래프 노드로 무의미. build_graph 취합 단계에서 제외."""
    return norm in ENTITY_STOPWORDS or bool(_NUMERIC_ONLY.match(norm))


def clean_entity_text(t: str) -> str:
    """앞뒤 구두점·한국어 끝 조사 제거 (PoC와 동일)."""
    cleaned = (t or "").strip().rstrip(",.;:")
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = _TRAILING_JOSA.sub("", cleaned).strip()
    return cleaned


def normalize_name(name: str) -> str:
    """병합 키: 공백 완전 제거 + casefold.
    공백변형(스마트 도시/스마트도시)·GLiNER2 깨진 span(소프트웨 어) 병합."""
    return _WS.sub("", (name or "").strip()).casefold()


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


def load_active_chunks(eng, limit, sample_per_doc=None):
    if sample_per_doc:
        # 문서당 최대 N청크 (전 문서·형식 커버하는 층화 샘플 — 다양성 검증용)
        sql = (
            "SELECT chunk_id, doc_content_id, txt FROM ("
            " SELECT ch.id AS chunk_id, ch.doc_content_id, ch.text AS txt,"
            " row_number() OVER (PARTITION BY ch.doc_content_id ORDER BY ch.chunk_index) rn"
            " FROM rag_chunks ch JOIN doc_document_content d ON ch.doc_content_id = d.id"
            " WHERE d.is_active = 'Y'"
            f") x WHERE rn <= {int(sample_per_doc)} ORDER BY doc_content_id, rn"
        )
    else:
        sql = (
            "SELECT ch.id AS chunk_id, ch.doc_content_id, ch.text "
            "FROM rag_chunks ch "
            "JOIN doc_document_content d ON ch.doc_content_id = d.id "
            "WHERE d.is_active = 'Y' "
            "ORDER BY ch.doc_content_id, ch.chunk_index"
        )
        if limit:
            sql += f" LIMIT {int(limit)}"
    with eng.connect() as c:
        rows = c.execute(text(sql)).fetchall()
    return [{"chunk_id": str(r[0]), "doc_content_id": str(r[1]), "text": r[2] or ""} for r in rows]


def extract_spans(extractor, schema_obj, txt):
    """청크 텍스트 → [(norm, surface, type), ...] (중복 span 포함)."""
    raw = extractor.extract(txt, schema_obj)
    out = []
    for label, spans in (raw.get("entities") or {}).items():
        etype = LABEL_TO_TYPE.get(label, "OTHER")
        if not isinstance(spans, list):
            continue
        for s in spans:
            if not isinstance(s, str) or len(s) > _MAX_SPAN_CHARS:
                continue
            name = clean_entity_text(s)
            if not name or len(name) <= 1:
                continue
            norm = normalize_name(name)
            if norm:
                out.append((norm, name, etype))
    return out


def extract_via_api(texts, url, key, batch_size=32, timeout=120, max_retries=4):
    """텍스트 배치를 GLiNER2 API(/extract)로 추출 → 텍스트별 [(norm, surface, type), ...].
    서버가 clean_entity_text 까지 수행하므로 여기선 normalize_name 만 적용.

    견고성(양산 16만 청크 대비): 배치별 connect/read 타임아웃 + 지수백오프 재시도.
    일시적 stall/끊김에 전체 빌드가 죽지 않도록 함. 재시도 모두 실패하면 명확히 raise
    (배치를 말없이 건너뛰지 않음 — 부분 그래프는 착시).
    """
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    endpoint = url.rstrip("/") + "/extract"
    sess = requests.Session()                       # 연결 재사용(keep-alive)
    out, n = [], len(texts)
    for i in range(0, n, batch_size):
        batch = texts[i:i + batch_size]
        bt = time.time()
        resp = None
        for attempt in range(1, max_retries + 1):
            try:
                # (connect=10s, read=timeout) — 느린 배치는 read 대기, 끊김은 connect에서 빠르게 표면화
                resp = sess.post(endpoint, json={"texts": batch}, headers=headers,
                                 timeout=(10, timeout))
                resp.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                if attempt == max_retries:
                    raise SystemExit(
                        f"[중단] GLiNER2 배치 {i}~{i+len(batch)} {max_retries}회 모두 실패: {e}\n"
                        f"  → NEXUS GLiNER2 앱 상태 확인: curl {url.rstrip('/')}/health")
                wait = min(2 ** attempt, 30)         # 2,4,8,16... 최대 30s
                print(f"    [재시도 {attempt}/{max_retries-1}] 배치 {i}~{i+len(batch)} 실패({type(e).__name__}), {wait}s 후 재시도", flush=True)
                time.sleep(wait)
        for res in resp.json().get("results", []):
            spans = []
            for e in (res.get("entities") or []):
                norm = normalize_name(e.get("name", ""))
                if norm:
                    spans.append((norm, e["name"], e.get("type", "OTHER")))
            out.append(spans)
        print(f"    추출 {min(i + batch_size, n)}/{n}  ({time.time()-bt:.1f}s/배치)", flush=True)
    return out


def _bulk_insert(conn, table, rows, batch=5000):
    for i in range(0, len(rows), batch):
        conn.execute(table.insert(), rows[i:i + batch])


def load_alias_map(eng):
    """엔티티 resolution 맵 로드 (build_alias_map.py 산출, summary_cache 단일행).
    반환 (amap: 변형norm→대표norm, names: 대표norm→대표surface). 없으면 ({},{}) = no-op."""
    with eng.connect() as c:
        row = c.execute(text(
            "SELECT summary_text FROM rag_graph_summary_cache WHERE cache_key='alias_map:v1'")).scalar()
    if not row:
        return {}, {}
    try:
        d = json.loads(row)
        return d.get("map", {}) or {}, d.get("names", {}) or {}
    except (ValueError, TypeError):
        return {}, {}


def main():
    # 파이프라인 실 시작시각. 빌드 row 는 추출(수십분)이 끝난 뒤 [6] 적재 트랜잭션에서
    # 생기므로, started_at 을 이 시점으로 소급 기록해야 소요시간이 실측된다.
    t_pipeline = time.monotonic()
    ap = argparse.ArgumentParser(description="그래프 백본 빌드 (LLM0/Qdrant0)")
    ap.add_argument("--db", default="dev", help="dev | prod")
    ap.add_argument("--limit", type=int, default=None, help="청크 수 제한 (스모크 테스트용)")
    ap.add_argument("--min-entity-len", type=int, default=2, help="최소 엔티티 글자 수")
    ap.add_argument("--keep-junk", action="store_true",
                    help="표 구조어(소계·산출근거·비고...)·순수숫자 엔티티를 제외하지 않고 유지"
                         " (기본은 제외). 필터 영향 비교/롤백용")
    ap.add_argument("--no-resolution", action="store_true",
                    help="alias resolution 맵 적용 안 함(변형 병합 비활성)")
    ap.add_argument("--min-edge-weight", type=int, default=1,
                    help="이 weight 미만 공출현 엣지 가지치기 (1=전부 유지, 스케일시 2+ 검토)")
    ap.add_argument("--edge-weight", choices=["raw", "pmi"], default="raw",
                    help="Louvain 군집 가중치: raw(공출현수) | pmi(npmi, 허브감쇠로 hairball 완화). "
                         "저장 edge.weight는 항상 raw (검색측 계약 불변)")
    ap.add_argument("--resolution", type=float, default=1.0,
                    help="Louvain 해상도: 높을수록 커뮤니티가 잘게 쪼개짐(hairball 완화). "
                         "1=기본, build20 실측상 10이면 최대군집 10.6k→1.1k로 분해(주제 코헤런스 유지)")
    ap.add_argument("--sample-per-doc", type=int, default=None,
                    help="문서당 N청크 층화 샘플 (전 형식 커버, 다양성 검증용)")
    ap.add_argument("--gliner-url", default=os.getenv("GLINER_API_URL"),
                    help="GLiNER2 추출 API URL (NEXUS, /extract 엔드포인트 보유). 미지정시 GLINER_API_URL 환경변수")
    ap.add_argument("--gliner-key", default=os.getenv("GLINER_API_KEY", ""),
                    help="GLiNER2 API Bearer 키 (필요시)")
    args = ap.parse_args()

    eng, db, schema = make_engine(args.db)
    print(f"[빌드 대상] db={db} schema={schema}")

    chunks = load_active_chunks(eng, args.limit, args.sample_per_doc)
    print(f"[1] 활성 청크 로드: {len(chunks)}개")
    if not chunks:
        raise SystemExit("활성 청크가 없습니다.")

    if not args.gliner_url:
        raise SystemExit("--gliner-url (또는 환경변수 GLINER_API_URL) 가 필요합니다.")
    print(f"[2] GLiNER2 API 추출 ({len(chunks)}청크): {args.gliner_url}")
    t0 = time.time()
    spans_per_chunk = extract_via_api([ch["text"] for ch in chunks], args.gliner_url, args.gliner_key)
    print(f"    → 추출 완료 {time.time() - t0:.0f}s")

    # 누적 구조
    ent_name = {}                            # norm -> 대표 surface (첫 등장)
    ent_type_votes = defaultdict(Counter)    # norm -> type 투표
    ent_chunk_occ = defaultdict(Counter)     # norm -> Counter({(chunk_id, doc_id): 등장수})
    chunk_entities = defaultdict(set)        # chunk_id -> set(norm)

    # resolution(alias) 맵: 변형 엔티티를 canonical로 접음(스마트도시=스마트시티 등). 없으면 no-op.
    amap, anames = ({}, {}) if args.no_resolution else load_alias_map(eng)
    if amap:
        print(f"    alias 맵 적용: 변형 {len(amap)}개 → canonical 치환")

    print(f"[3] 엔티티 취합...")
    n_collapsed = 0
    n_junk = 0
    junk_seen = set()
    for ch, spans in zip(chunks, spans_per_chunk):
        cid, did = ch["chunk_id"], ch["doc_content_id"]
        for norm, surface, etype in spans:
            if len(norm) < args.min_entity_len:
                continue
            # 표 구조 라벨·순수 숫자 제외 (도메인 용어는 보존 — is_junk_entity 주석 참고)
            if not args.keep_junk and is_junk_entity(norm):
                n_junk += 1
                junk_seen.add(norm)
                continue
            canon = amap.get(norm)
            if canon:
                norm = canon; surface = anames.get(canon, surface); n_collapsed += 1
            ent_name.setdefault(norm, surface)
            if norm in anames:                 # canonical 표기 일관성
                ent_name[norm] = anames[norm]
            ent_type_votes[norm][etype] += 1
            ent_chunk_occ[norm][(cid, did)] += 1
            chunk_entities[cid].add(norm)
    print(f"    → 고유 엔티티 {len(ent_name)}" + (f" (resolution으로 {n_collapsed}회 치환)" if amap else ""))
    if n_junk:
        print(f"    표 구조어·숫자 제외: span {n_junk}건 / 고유 {len(junk_seen)}종")

    # 문서별 통계 (그래프 처리 상태 추적용 — rag_graph_doc_status)
    doc_chunks = defaultdict(set)   # doc_id -> 로드된 chunk_id 집합
    for ch in chunks:
        doc_chunks[ch["doc_content_id"]].add(ch["chunk_id"])
    doc_entities = defaultdict(set)  # doc_id -> 추출된 norm 집합
    for norm, occ in ent_chunk_occ.items():
        for (cid, did), _ in occ.items():
            doc_entities[did].add(norm)

    # 공출현 엣지 (같은 청크 동시 등장 쌍, co=공출현 청크 수)
    edge_co_all = defaultdict(int)
    for cid, norms in chunk_entities.items():
        for a, b in combinations(sorted(norms), 2):
            edge_co_all[(a, b)] += 1
    # 가지치기는 raw 공출현 수 기준 ("함께 등장한 청크 수" 하한)
    edge_co = {k: c for k, c in edge_co_all.items() if c >= args.min_edge_weight}
    print(f"[4] 공출현 엣지: {len(edge_co_all)} → {len(edge_co)} (min_weight={args.min_edge_weight})")

    # 저장 weight = 항상 raw 공출현 수 (검색측 계약 불변).
    edge_w = dict(edge_co)

    # Louvain 입력 가중치: raw(공출현) | pmi(npmi). npmi는 허브쌍을 0으로 감쇠해
    # hairball 분해를 노린 실험 — 저장 weight엔 영향 없음(군집화 입력만 교체).
    if args.edge_weight == "pmi":
        n_chunks = max(len(chunks), 1)
        ent_freq = {norm: len(occ) for norm, occ in ent_chunk_occ.items()}  # norm 포함 청크 수
        louvain_w = {}
        for (a, b), co in edge_co.items():
            p_ab = co / n_chunks
            pmi = math.log((co * n_chunks) / (ent_freq[a] * ent_freq[b]))
            denom = -math.log(p_ab)                          # = -log P(a,b)
            npmi = 1.0 if denom <= 1e-12 else pmi / denom    # [-1,1], 독립=0
            louvain_w[(a, b)] = max(npmi, 0.0)               # 양수만(허브쌍≈0 → 군집기여 소거)
        nz = sum(1 for v in louvain_w.values() if v > 0.0)
        print(f"    → Louvain 가중치=npmi (양수 {nz}/{len(louvain_w)})")
    else:
        louvain_w = {k: float(c) for k, c in edge_co.items()}

    # Louvain 커뮤니티 (고립 엔티티도 노드 포함 → 싱글톤 커뮤니티)
    G = nx.Graph()
    for (a, b), w in louvain_w.items():
        G.add_edge(a, b, weight=w)
    for norm in ent_name:
        if norm not in G:
            G.add_node(norm)
    comms = louvain_communities(G, weight="weight", resolution=args.resolution, seed=42)
    comms.sort(key=lambda c: -len(c))
    norm_to_comm = {norm: idx for idx, cset in enumerate(comms) for norm in cset}
    giant = len(comms[0]) if comms else 0
    print(f"[5] 커뮤니티(Louvain, w={args.edge_weight}, res={args.resolution}): {len(comms)}  "
          f"상위 sizes={[len(c) for c in comms[:8]]}  "
          f"최대군집 {giant}/{len(ent_name)} ({100*giant/max(len(ent_name),1):.1f}%)")

    # ── RDB 적재 (단일 트랜잭션) ──
    print("[6] RDB 적재...")
    norm_to_eid = {norm: uuid.uuid4() for norm in ent_name}
    comm_ids = {idx: uuid.uuid4() for idx in range(len(comms))}

    with eng.begin() as conn:
        # started_at: DEFAULT now() 는 "적재 트랜잭션 시작"이라 추출시간이 빠진다 →
        # 경과초를 빼서 파이프라인 실 시작으로 소급. 전부 DB측 계산이므로 naive datetime·
        # 타임존 이슈가 없다(now() 는 트랜잭션 시작시각이라 clock_timestamp() 사용).
        bid = conn.execute(
            text("INSERT INTO rag_graph_builds (status, corpus_chunk_count, started_at) "
                 "VALUES ('building', :n, clock_timestamp() - make_interval(secs => :el)) "
                 "RETURNING id"),
            {"n": len(chunks), "el": time.monotonic() - t_pipeline},
        ).scalar()

        comm_rows = [{
            "id": comm_ids[idx], "build_id": bid, "level": 0,
            "label": None, "summary": None, "entity_count": len(cset),
        } for idx, cset in enumerate(comms)]
        if comm_rows:
            conn.execute(m.GraphCommunity.__table__.insert(), comm_rows)

        ent_rows = []
        for norm, eid in norm_to_eid.items():
            etype = ent_type_votes[norm].most_common(1)[0][0]
            ent_rows.append({
                "id": eid, "build_id": bid,
                "name": ent_name[norm], "entity_type": etype,
                "normalized_name": norm, "qdrant_point_id": None,
                "community_id": comm_ids.get(norm_to_comm.get(norm)),
                "chunk_count": len(ent_chunk_occ[norm]),
            })
        conn.execute(m.GraphEntity.__table__.insert(), ent_rows)

        ec_rows = []
        for norm, occ in ent_chunk_occ.items():
            eid = norm_to_eid[norm]
            for (cid, did), n in occ.items():
                ec_rows.append({
                    "build_id": bid, "entity_id": eid,
                    "chunk_id": cid, "doc_content_id": did,
                    "occurrence_count": n,
                })
        _bulk_insert(conn, m.GraphEntityChunk.__table__, ec_rows)

        edge_rows = [{
            "build_id": bid,
            "source_entity_id": norm_to_eid[a],
            "target_entity_id": norm_to_eid[b],
            "weight": float(w),
        } for (a, b), w in edge_w.items()]
        _bulk_insert(conn, m.GraphEdge.__table__, edge_rows)

        # 문서별 그래프 처리 상태 (어느 문서가 그래프됐나 — embedding status 의 그래프 버전)
        fn_map = {str(r[0]): r[1] for r in conn.execute(
            text("SELECT id, original_filename FROM doc_document_content WHERE id IN :ids")
            .bindparams(bindparam("ids", expanding=True)), {"ids": list(doc_chunks.keys())})}
        status_rows = []
        for did, cset in doc_chunks.items():
            ne = len(doc_entities.get(did, ()))
            status_rows.append({
                "build_id": bid, "doc_content_id": did, "original_filename": fn_map.get(did),
                "status": "done" if ne > 0 else "no_entities",
                "chunk_count": len(cset), "entity_count": ne,
            })
        if status_rows:
            conn.execute(m.GraphDocStatus.__table__.insert(), status_rows)

        # 이번 빌드의 실행 노브 — 어떤 파라미터로 만든 그래프인지 사후 추적용(계약 문서가
        # params 존재를 안내 중). 튜닝 회귀를 DB만 보고 판별할 수 있게 한다.
        build_params = {
            "min_edge_weight": args.min_edge_weight,
            "edge_weight": args.edge_weight,
            "resolution": args.resolution,
            "limit": args.limit,
            "sample_per_doc": args.sample_per_doc,
            "min_entity_len": args.min_entity_len,
            "alias_pairs": len(amap),
            "gliner_model": MODEL_NAME,
            # 스톱워드 필터 적용 여부·규모 — 엔티티 수 변화를 사후에 이걸로 설명할 수 있게
            "junk_filter": (not args.keep_junk),
            "junk_stopwords": len(ENTITY_STOPWORDS),
            "junk_dropped_kinds": len(junk_seen),
        }

        # 이전 active → superseded, 이번 빌드 → active
        # finished_at 은 clock_timestamp() — now() 는 트랜잭션 시작시각이라 started_at 과
        # 동일해져 소요시간이 0 으로 보인다. 의미상 "구조 빌드 완료 = active 스왑 시점"이고
        # 이후 enrich 단계(관계라벨·설명)는 active 빌드에 계속 채워진다.
        conn.execute(text("UPDATE rag_graph_builds SET status='superseded' WHERE status='active'"))
        conn.execute(
            text("UPDATE rag_graph_builds SET status='active', finished_at=clock_timestamp(), "
                 "entity_count=:e, edge_count=:g, community_count=:c, "
                 "params=CAST(:p AS jsonb) WHERE id=:b"),
            {"e": len(ent_rows), "g": len(edge_rows), "c": len(comms),
             "p": json.dumps(build_params, ensure_ascii=False), "b": bid},
        )

    print(f"    → build_id={bid} active. "
          f"엔티티 {len(ent_rows)} / 엣지 {len(edge_rows)} / 커뮤니티 {len(comms)} / 라우팅 {len(ec_rows)}")
    print("[완료]")


if __name__ == "__main__":
    main()
