#!/usr/bin/env bash
# Dev parent 백필 (embedd-vm). prod 이미지/설정 재활용 + dev 타겟으로 env 오버라이드.
#   bash run_backfill_dev.sh        -> dry-run(limit5, 쓰기 없음, 타겟 확인용)
#   bash run_backfill_dev.sh apply  -> 전체 실행(--apply)
# dev 타겟: DB=ragdb_dev, schema=rag_dev, Qdrant=rag_chunks_v1_dev, 체크포인트=dev 전용(분리)
set -euo pipefail
cd /home/ubuntu/embedd-graph

MODE="${1:-dry}"
if [ "$MODE" = "apply" ]; then RUN_ARGS="--apply"; else RUN_ARGS="--limit 5"; fi

echo "=== DEV backfill: mode=$MODE  target=ragdb_dev/rag_dev  coll=rag_chunks_v1_dev ==="
docker compose -f docker-compose.prod-graph.yml run --rm -T \
  -v /home/ubuntu/embedd-graph/backfill_parents_opt.py:/app/scripts/parent_backfill/backfill_parents.py \
  -e POSTGRES_DB=ragdb_dev \
  -e POSTGRES_SCHEMA=rag_dev \
  -e QDRANT_COLLECTION=rag_chunks_v1_dev \
  -e PARENT_CKPT=/app/logs/parent_checkpoint_dev.json \
  graph-build python scripts/parent_backfill/backfill_parents.py $RUN_ARGS
