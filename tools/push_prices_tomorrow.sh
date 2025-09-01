PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
#!/usr/bin/env bash
set -euo pipefail
source /home/runerova/.arrigo.env

for i in {1..6}; do
  if /usr/bin/python3 /home/runerova/smartweb/tools/exo_price_rank.py \
      --site-id C1 \
      --login-url "$ARRIGO_LOGIN_URL" --graphql-url "$ARRIGO_GRAPHQL_URL" \
      --pvl-path "$ARRIGO_PVL_PATH" --arrigo-user "$ARRIGO_USER" --arrigo-pass "$ARRIGO_PASS" \
      --day "$(date -d tomorrow +%F)" --push; then
  echo "$(date '+%F %T') ✅ PUSH OK (tomorrow)" >> /home/runerova/smartweb/spotpris_push.log
    exit 0
  fi
  echo "$(date '+%F %T') Inga priser ännu – försöker igen om 30 min" >> /home/runerova/smartweb/spotpris_push.log
  sleep 1800
done

echo "$(date '+%F %T') Avbröt efter 6 försök (3h) – priser saknas" >> /home/runerova/smartweb/spotpris_push.log
exit 1
