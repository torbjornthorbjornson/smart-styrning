#!/bin/bash
set -e

BASE=~/smartweb/tools/arrigo
BACKUP_DIR="$BASE/backup/$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

echo "📦 Skapar backup i $BACKUP_DIR"

for f in orchestrator.py push_from_db.py readback_vvplan_to_db.py readback_heatplan_to_db.py; do
  if [ -f "$BASE/$f" ]; then
    cp "$BASE/$f" "$BACKUP_DIR/"
    echo "  ✔ $f"
  else
    echo "  ⚠ $f saknas – hoppad över"
  fi
done

echo "✅ Backup klar"
