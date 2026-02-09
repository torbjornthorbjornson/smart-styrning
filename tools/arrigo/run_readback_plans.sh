#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$DIR/logs"
LOG_FILE="$LOG_DIR/arrigo_readback.log"

mkdir -p "$LOG_DIR"

# Load Arrigo env (URLs, credentials, PVL etc)
if [[ -f "/home/runerova/.arrigo.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "/home/runerova/.arrigo.env"
  set +a
fi

PY="/home/runerova/myenv/bin/python3"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

run_one() {
  local script="$1"
  local max_tries="${2:-3}"
  local try=1

  while (( try <= max_tries )); do
    echo "===== $(date -Is) READBACK $script try=$try/$max_tries =====" >> "$LOG_FILE"

    # Keep logs unbuffered, and ensure we don't hang forever.
    if timeout 75s env PYTHONUNBUFFERED=1 "$PY" "$DIR/$script" >> "$LOG_FILE" 2>&1; then
      return 0
    fi

    echo "WARN: $script failed (try=$try)" >> "$LOG_FILE"
    sleep 5
    ((try++))
  done

  echo "ERROR: $script failed after $max_tries tries" >> "$LOG_FILE"
  return 1
}

run_one "readback_vvplan_to_db.py" 3
run_one "readback_heatplan_to_db.py" 3

echo "===== $(date -Is) READBACK DONE =====" >> "$LOG_FILE"
