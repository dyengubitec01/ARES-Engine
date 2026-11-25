#!/usr/bin/env bash
# 그래프 빌드 오케스트레이션 (컨테이너 내부 실행) — 구조 → 엔티티벡터 → LLM요약 순차.
# URL/키는 환경변수(GLINER_API_URL/GEMMA_API_URL/...)에서 읽음(스크립트가 os.getenv 기본값).
set -euo pipefail
cd /app

DB="${GRAPH_DB:-dev}"
MAX_EDGES="${MAX_EDGES:-50}"
MIN_COMMUNITY_SIZE="${MIN_COMMUNITY_SIZE:-3}" # 엔티티 이 수 이상 커뮤니티만 요약(임계값,상한없음). 1·2 제외(2=단일관계=라벨몫), 3+=그룹
RELATION_WORKERS="${RELATION_WORKERS:-32}"   # per-chunk 관계추출 동시성(gemma 포화 ~32)
RELATION_MIN_ENT="${RELATION_MIN_ENT:-2}"    # 엔티티 이 수 이상 청크만 관계콜(2=쌍도 포함, +7%로 저렴)
RELATION_MAX_ENT_PER_CALL="${RELATION_MAX_ENT_PER_CALL:-40}"  # 콜당 엔티티 상한(리스트청크 출력절단 방지)
RELATION_EXTRACT="${RELATION_EXTRACT:-1}"    # 0=관계추출 스킵(구조만)
ENTITY_DESC="${ENTITY_DESC:-1}"              # 0=엔티티 설명 스킵
DESC_MIN_CHUNK_COUNT="${DESC_MIN_CHUNK_COUNT:-2}"  # 이 청크수 이상 엔티티만 설명(1=재료 한문장뿐 제외)
RESOLUTION_REFRESH="${RESOLUTION_REFRESH:-1}" # 매빌드 alias(resolution) 맵 갱신(다음 빌드 적용용). 0=스킵
ALIAS_TOPN="${ALIAS_TOPN:-20000}"            # alias 맵 대상 고빈도 엔티티 수
GC_KEEP_SUPERSEDED="${GC_KEEP_SUPERSEDED:-1}" # active 외 보존할 직전 빌드 수(롤백용). 1=어제만, 0=정리만/롤백없음

# GRAPH_LIMIT 설정 시 build_graph 청크 수 제한(스모크 테스트용). 미설정=전체.
LIMIT_ARG=""
if [ -n "${GRAPH_LIMIT:-}" ]; then
    LIMIT_ARG="--limit ${GRAPH_LIMIT}"
fi

# MIN_EDGE_WEIGHT 설정 시 약한 공출현 엣지 가지치기(스케일 대응). 미설정=1(전부 유지).
WEIGHT_ARG=""
if [ -n "${MIN_EDGE_WEIGHT:-}" ]; then
    WEIGHT_ARG="--min-edge-weight ${MIN_EDGE_WEIGHT}"
fi

# Louvain 군집 가중치: 기본 pmi(npmi, 허브감쇠로 hairball 완화 — 운영 표준, build9 검증).
# raw로 끄려면 EDGE_WEIGHT=raw. 저장 edge.weight는 항상 raw(검색측 계약 불변).
EDGE_WEIGHT="${EDGE_WEIGHT:-pmi}"
EDGEW_ARG="--edge-weight ${EDGE_WEIGHT}"

# Louvain 해상도: 높을수록 커뮤니티가 잘게 쪼개짐(hairball 완화). 기본 1(하위호환).
# build20 실측: res=10이면 최대군집 10.6k→1.1k로 분해, 주제 코헤런스 유지(res15부터 미세 노이즈).
RESOLUTION="${RESOLUTION:-1}"
RES_ARG="--resolution ${RESOLUTION}"

echo "===== graph pipeline 시작 (DB=$DB, LIMIT=${GRAPH_LIMIT:-전체}, MIN_EDGE_WEIGHT=${MIN_EDGE_WEIGHT:-1}, EDGE_WEIGHT=${EDGE_WEIGHT}, RESOLUTION=${RESOLUTION}) $(date) ====="

echo "[1/4] build_graph — 구조(클라우드 GLiNER2 + 사내 청크)"
python scripts/graph_build/build_graph.py --db "$DB" $LIMIT_ARG $WEIGHT_ARG $EDGEW_ARG $RES_ARG

echo "[2/4] embed_entities — 엔티티 벡터(사내 BGE-M3 → Qdrant)"
python scripts/graph_build/embed_entities.py --db "$DB"

# resolution(alias) 맵 갱신 — 이번 빌드 엔티티벡터로 {변형→대표} 재계산(cosine+alias+숫자가드).
# 맵은 다음 빌드 build_graph가 로드해 적용(norm 키라 cross-build). 첫 적용엔 사전 1회 빌드 필요.
if [ "$RESOLUTION_REFRESH" = "1" ]; then
    echo "[+] build_alias_map — resolution 맵 갱신(다음 빌드 적용용)"
    python scripts/graph_build/build_alias_map.py --db "$DB" --topn "$ALIAS_TOPN"
fi

echo "[3/4] summarize_graph — LLM 요약(클라우드 gemma4, 커뮤니티 엔티티>=${MIN_COMMUNITY_SIZE})"
python scripts/graph_build/summarize_graph.py --db "$DB" \
    --max-edges "$MAX_EDGES" --min-community-size "$MIN_COMMUNITY_SIZE" \
    || echo "[!] summarize_graph 실패(비치명적) — 파이프라인 계속 진행"

# 관계라벨링(긴 단계, ~첫빌드 10h/이후 델타). 캐시(rag_graph_summary_cache)로 재개·델타.
# 구조/벡터/요약이 먼저 끝나 active 빌드는 즉시 사용 가능, 관계라벨은 enrich로 채워짐.
if [ "$RELATION_EXTRACT" = "1" ]; then
    echo "[4/4] extract_relations — per-chunk 관계라벨(클라우드 gemma4, workers=$RELATION_WORKERS)"
    python scripts/graph_build/extract_relations.py --db "$DB" --store \
        --workers "$RELATION_WORKERS" --min-ent "$RELATION_MIN_ENT" \
        --max-ent-per-call "$RELATION_MAX_ENT_PER_CALL" \
        || echo "[!] extract_relations 실패(비치명적) — 파이프라인 계속 진행"
else
    echo "[4/4] extract_relations — 스킵(RELATION_EXTRACT=0)"
fi

# 엔티티 설명(per-entity LLM, 캐시로 첫빌드 후 델타). 관계라벨 *뒤*에 두고 비치명적(|| true)으로
# — describe 실패가 파이프라인(라벨링·GC)을 절대 못 깨게. chunk_count>=N만(1청크=재료부족 제외).
if [ "$ENTITY_DESC" = "1" ]; then
    echo "[+] describe_entities — 엔티티 설명(클라우드 gemma4, chunk_count>=${DESC_MIN_CHUNK_COUNT}, workers=$RELATION_WORKERS)"
    python scripts/graph_build/describe_entities.py --db "$DB" \
        --workers "$RELATION_WORKERS" --min-chunk-count "$DESC_MIN_CHUNK_COUNT" \
        || echo "[!] describe_entities 실패(비치명적) — 파이프라인 계속 진행"
fi

# 옛 빌드 GC — 전 단계 성공 후에만 도달(set -e). active + 직전 GC_KEEP_SUPERSEDED개만 남기고
# 오래된 superseded 삭제. 매빌드 누적 방지. raguser DML로 DELETE(공간회수는 autovacuum).
echo "[+] gc_old_builds — 옛 빌드 정리 (active + 직전 ${GC_KEEP_SUPERSEDED}개 보존)"
python scripts/graph_build/gc_old_builds.py --db "$DB" --keep-superseded "$GC_KEEP_SUPERSEDED"

echo "===== graph pipeline 완료 $(date) ====="
