#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "$0")" && pwd -P)"
PY="$SELF_DIR/exo_price_rank_array.py"
source /home/runerova/.arrigo.env

EXTRA=()
if [[ "${ARRIGO_INSECURE:-}" == "1" ]]; then EXTRA+=(--insecure); fi

python3 $PY \
  --site-id C1 \
  --login-url "$ARRIGO_LOGIN_URL" --graphql-url "$ARRIGO_GRAPHQL_URL" \
  --pvl-path "$ARRIGO_PVL_PATH" --arrigo-user "$ARRIGO_USER" --arrigo-pass "$ARRIGO_PASS" \
  --verify "${EXTRA[@]}" | grep -E 'PRICE_OK|PRICE_STAMP|PRICE_RANK_' -A1
