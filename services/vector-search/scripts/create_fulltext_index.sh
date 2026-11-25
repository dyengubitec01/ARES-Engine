#!/usr/bin/env bash
#
# Qdrant text_for_search full-text payload index 생성 + 확인 스크립트
#
# Hybrid Search(Dense + Qdrant full-text + RRF)를 켜려면 컬렉션마다 1회 필요.
# 앱은 인덱스를 생성하지 않음 (검색 전용 원칙) — 운영자가 수동 실행.
#
# idempotent: 동일 스키마면 Qdrant가 no-op 처리.
#
# Usage:
#   QDRANT_URL=http://localhost:6333 \
#   COLLECTION=rag_chunks_v1 \
#     bash scripts/create_fulltext_index.sh
#
# 또는 환경변수 없이 실행하면 아래 기본값 사용 (prod).

set -euo pipefail

QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
COLLECTION="${COLLECTION:-rag_chunks_v1}"
FIELD="text_for_search"

echo "==> create fulltext index: ${QDRANT_URL}/collections/${COLLECTION} field=${FIELD}"

curl -sS -X PUT "${QDRANT_URL}/collections/${COLLECTION}/index" \
  -H "Content-Type: application/json" \
  -d "{\"field_name\":\"${FIELD}\",\"field_schema\":{\"type\":\"text\",\"tokenizer\":\"multilingual\",\"min_token_len\":2,\"max_token_len\":20,\"lowercase\":true}}"
echo
echo

echo "==> verify payload_schema.${FIELD}"
curl -sS "${QDRANT_URL}/collections/${COLLECTION}" \
  | python -c "import sys,json; info=json.load(sys.stdin)['result']; print(info.get('payload_schema',{}).get('${FIELD}','NOT_FOUND'))"

# 기대 응답:
#   create: {"result":{"operation_id":N,"status":"acknowledged"},"status":"ok",...}
#   verify: {'data_type': 'text', 'params': {'type': 'text', 'tokenizer': 'multilingual', ...}, 'points': <N>}
# NOT_FOUND 가 뜨면 실패.
