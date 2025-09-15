PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
#!/usr/bin/env bash
set -euo pipefail
source /home/runerova/.arrigo.env
/usr/bin/python3 /home/runerova/smartweb/tools/old_rank/exo_price_rank.py \
  --site-id C1 \
  --login-url   "$ARRIGO_LOGIN_URL" \
  --graphql-url "$ARRIGO_GRAPHQL_URL" \
  --pvl-path    "$ARRIGO_PVL_PATH" \
  --arrigo-user "$ARRIGO_USER" \
  --arrigo-pass "$ARRIGO_PASS" \
  --push
echo "$(date "+%F %T") ✅ PUSH OK (today)" >> /home/runerova/smartweb/spotpris_push.log
