#!/usr/bin/env bash
set -euo pipefail
source /home/runerova/.arrigo.env
python3 /home/runerova/smartweb/tools/exo_price_rank.py \
  --site-id C1 \
  --login-url "$ARRIGO_LOGIN_URL" --graphql-url "$ARRIGO_GRAPHQL_URL" \
  --pvl-path "$ARRIGO_PVL_PATH" --arrigo-user "$ARRIGO_USER" --arrigo-pass "$ARRIGO_PASS" \
  --verify | grep -E 'PRICE_OK|PRICE_STAMP' -A1
