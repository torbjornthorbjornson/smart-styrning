#!/usr/bin/env -S bash -euo pipefail
# ^ Shebang måste vara rad 1. -S låter oss sätta flaggor direkt.

# Miljö
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export TZ=Europe/Stockholm

# Ladda Arrigo-sekret
# Se till att .arrigo.env har rader på formen: export ARRIGO_LOGIN_URL=...
source /home/runerova/.arrigo.env

LOG=/home/runerova/smartweb/spotpris_push.log
PY=/usr/bin/python3
TOOL=/home/runerova/smartweb/tools/exo_price_rank.py

# Försök upp till 6 gånger, 30 min emellan (totalt 3h)
for i in {1..6}; do
  if "$PY" "$TOOL" \
      --site-id C1 \
      --login-url "$ARRIGO_LOGIN_URL" \
      --graphql-url "$ARRIGO_GRAPHQL_URL" \
      --pvl-path "$ARRIGO_PVL_PATH" \
      --arrigo-user "$ARRIGO_USER" \
      --arrigo-pass "$ARRIGO_PASS" \
      --day "$(date -d tomorrow +%F)" \
      --push >>"$LOG" 2>&1; then
    echo "$(date '+%F %T') ✅ PUSH OK (tomorrow)" >> "$LOG"
    exit 0
  fi
  echo "$(date '+%F %T') Inga priser ännu – försöker igen om 30 min" >> "$LOG"
  sleep 1800
done

echo "$(date '+%F %T') Avbröt efter 6 försök (3h) – priser saknas" >> "$LOG"
exit 1
