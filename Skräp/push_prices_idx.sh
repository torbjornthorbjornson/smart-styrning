#!/usr/bin/env bash
set -euo pipefail
source ~/.arrigo.env
source ~/myenv/bin/activate

python3 /home/runerova/smartweb/tools/old_rank/exo_price_rank.py \
  --site-id C1 \
  --login-url   "$ARRIGO_LOGIN_URL" \
  --graphql-url "$ARRIGO_GRAPHQL_URL" \
  --pvl-path    "$ARRIGO_PVL_PATH" \
  --arrigo-user "$ARRIGO_USER" \
  --arrigo-pass "$ARRIGO_PASS" \
  --out - > /tmp/payload.json

python3 ~/smartweb/tools/old_rank/push_index_min.py
