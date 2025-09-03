#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="/home/runerova/smartweb"
BRANCH="main"
LOGFILE="$REPO_DIR/git_backup.log"

cd "$REPO_DIR"
git config user.name  "runerova-auto"
git config user.email "runerova@local"

git add -A

if ! git diff --cached --quiet; then
  TS="$(date '+%Y-%m-%d %H:%M:%S')"
  git commit -m "Auto-backup: $TS"
  git pull --rebase origin "$BRANCH" || true
  git push origin "$BRANCH"
  echo "$TS  committed & pushed" >> "$LOGFILE"
else
  echo "$(date '+%Y-%m-%d %H:%M:%S')  no changes" >> "$LOGFILE"
fi

