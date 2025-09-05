#!/usr/bin/env bash
set -euo pipefail
source /home/runerova/.arrigo.env

/usr/bin/python3 /home/runerova/smartweb/tools/new_rank/exo_price_rank_array.py \
  --site-id C1 \
  --login-url   "$ARRIGO_LOGIN_URL" \
  --graphql-url "$ARRIGO_GRAPHQL_URL" \
  --pvl-path    "$ARRIGO_PVL_PATH" \
  --arrigo-user "$ARRIGO_USER" \
  --arrigo-pass "$ARRIGO_PASS" \
  --push

echo "$(date "+%F %T") ✅ PUSH OK (today, array)" >> /home/runerova/smartweb/spotpris_push_array.log
