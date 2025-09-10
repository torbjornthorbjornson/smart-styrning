#!/usr/bin/env bash
set -euo pipefail
REPORT_DIR="${HOME}/smartweb/tools/sys/reports"
mkdir -p "$REPORT_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT="${REPORT_DIR}/audit_${STAMP}.txt"

{
  echo "=== DISKANVÄNDNING ==="
  df -h

  echo -e "\n=== STÖRSTA MAPPAR I HEMKATALOG (TOP 30) ==="
  du -xh ${HOME} | sort -h | tail -n 30

  echo -e "\n=== APT-cache ==="
  sudo du -sh /var/cache/apt/archives || true

  echo -e "\n=== Pip-cache ==="
  du -sh ${HOME}/.cache/pip || true

  echo -e "\n=== NPM-cache ==="
  du -sh ${HOME}/.npm || true

  echo -e "\n=== Journalctl storlek ==="
  sudo journalctl --disk-usage || true

  echo -e "\n=== Stora loggfiler (>100MB) i /var/log ==="
  sudo find /var/log -type f -size +100M -printf '%p\t%k KB\n' 2>/dev/null | sort -nk2

  echo -e "\n=== Virtuella miljöer (kandidater) i hemkatalog ==="
  find ${HOME} -maxdepth 2 -type d -regex '.*\(venv\|env\|\.venv\|myenv\).*' -print

  echo -e "\n=== Aktiverade systemd-tjänster ==="
  systemctl list-unit-files --type=service --state=enabled

} | tee "$REPORT"

echo "Rapport: $REPORT"
