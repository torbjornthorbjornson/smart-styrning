#!/usr/bin/env bash
set -euo pipefail

cd /home/runerova/smartweb

LOGDIR="/home/runerova/smartweb/tools/arrigo/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/arrigo_readback.log"

{
  echo "===== $(date -Is) READBACK START ====="
  /usr/bin/env python3 tools/arrigo/readback_vvplan_to_db.py
  /usr/bin/env python3 tools/arrigo/readback_heatplan_to_db.py
  echo "===== $(date -Is) READBACK DONE ====="
  echo
} >> "$LOG" 2>&1
