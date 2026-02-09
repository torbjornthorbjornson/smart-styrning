#!/usr/bin/env bash
set -euo pipefail

# Runs smartweb runtime verification and notifies on failure.
#
# Notification targets:
# - Always: append to smartweb/logs/verify_runtime.log and syslog via `logger`
# - Optional: Home Assistant persistent notification or notify service
#
# Env:
#   SMARTWEB_VERIFY_URL_BASE   (default http://127.0.0.1:8000)
#   SMARTWEB_PYTHON            (default /home/runerova/myenv/bin/python3)
#   SMARTWEB_HA_URL            (e.g. http://homeassistant.local:8123)
#   SMARTWEB_HA_TOKEN          (Long-Lived Access Token)
#   SMARTWEB_HA_NOTIFY_SERVICE (optional; e.g. mobile_app_iphone). If set, uses notify/<service>.

BASE_DIR="/home/runerova/smartweb"
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/verify_runtime.log"

mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

notify_ha() {
  local title="$1"
  local message="$2"

  local ha_url="${SMARTWEB_HA_URL:-}"
  local ha_token="${SMARTWEB_HA_TOKEN:-}"
  if [[ -z "$ha_url" || -z "$ha_token" ]]; then
    return 0
  fi

  local endpoint
  local payload

  if [[ -n "${SMARTWEB_HA_NOTIFY_SERVICE:-}" ]]; then
    endpoint="$ha_url/api/services/notify/${SMARTWEB_HA_NOTIFY_SERVICE}"
  else
    endpoint="$ha_url/api/services/persistent_notification/create"
  fi

  payload=$(python3 - "$title" "$message" <<'PY'
import json
import sys

title = sys.argv[1]
message = sys.argv[2]
print(json.dumps({"title": title, "message": message}, ensure_ascii=False))
PY
  )

  # shellcheck disable=SC2086
  curl -fsS \
    -H "Authorization: Bearer $ha_token" \
    -H "Content-Type: application/json" \
    -X POST \
    -d "$payload" \
    "$endpoint" >/dev/null || true
}

run_verify() {
  local out
  local rc=0

  out=$(SMARTWEB_URL_BASE="${SMARTWEB_VERIFY_URL_BASE:-http://127.0.0.1:8000}" \
        SMARTWEB_PYTHON="${SMARTWEB_PYTHON:-/home/runerova/myenv/bin/python3}" \
        "$BASE_DIR/scripts/verify_runtime.sh" 2>&1) || rc=$?

  echo "$out"
  return $rc
}

output=$(run_verify) || {
  rc=$?
  line="$(ts) FAIL verify_runtime rc=$rc"
  {
    echo "$line"
    echo "$output"
    echo
  } >> "$LOG_FILE"

  logger -t smartweb-verify "FAIL rc=$rc (see $LOG_FILE)"

  notify_ha "Smartweb: verifiering FAIL" "rc=$rc\n\n${output}" || true
  exit $rc
}

# Success path: keep it quiet (log only a one-liner)
echo "$(ts) OK" >> "$LOG_FILE"
exit 0
