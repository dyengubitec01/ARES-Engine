#!/usr/bin/env bash
# Parent 백필 진행 라이브 뷰 (embedd-vm에서 실행).
#   ssh -t ubuntu@localhost /home/ubuntu/embedd-graph/logs/watch_backfill.sh
# 종료: Ctrl+C (뷰만 닫힘, 백필은 계속 돎). 인자 "once" = 1회만 출력.
C=/home/ubuntu/embedd-graph/logs/parent_checkpoint.json
L=/home/ubuntu/embedd-graph/logs/parent_backfill.log
IMG=registry.example.com/ares/ew-graph:latest
TOTAL=1013

render() {
  local D P NOTE UP PCT BAR
  D=$(grep -oE '[0-9a-f-]{36}' "$C" 2>/dev/null | wc -l | tr -d ' ')
  P=$(grep -aoE '\[[0-9]+/[0-9]+\] doc=[0-9a-f-]+' "$L" 2>/dev/null | tail -1)
  NOTE=$(grep -aE 'fail:|OperationalError|retry|재시도' "$L" 2>/dev/null | tail -1)
  UP=$(docker ps --format '{{.Status}}' --filter ancestor="$IMG" | head -1)
  PCT=$(awk "BEGIN{if($TOTAL>0)printf \"%.1f\",$D/$TOTAL*100}")
  BAR=$(awk "BEGIN{n=int(40*$D/$TOTAL);for(i=0;i<n;i++)printf\"#\";for(i=n;i<40;i++)printf\"-\"}")
  [ "$1" != "once" ] && clear
  echo "=== Parent backfill 진행 (embedd-vm)  $(date +%H:%M:%S) ==="
  echo
  echo "  [$BAR] ${PCT}%"
  echo "  done ${D} / ${TOTAL}   (remaining ~$((TOTAL - D)))"
  echo "  current : ${P:-...}"
  echo "  container: ${UP:-<not running = 완료 또는 중단>}"
  [ -n "$NOTE" ] && echo "  last note: $NOTE"
  echo
  echo "  (Ctrl+C = 뷰 종료, 백필은 계속 돎)"
}

if [ "$1" = "once" ]; then render once; exit 0; fi
while true; do render; sleep 3; done
