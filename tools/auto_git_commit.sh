#!/usr/bin/env bash
set -euo pipefail

# Auto-commit loop for this repo.
# Usage: ./tools/auto_git_commit.sh [interval_seconds]

interval_seconds="${1:-300}"

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: $repo_dir is not a git repo" >&2
  exit 1
fi

warned_no_upstream=0

while true; do
  # Stage everything except ignored files
  git add -A

  # Anything staged?
  if git diff --cached --quiet; then
    sleep "$interval_seconds"
    continue
  fi

  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  host="$(hostname -s 2>/dev/null || hostname || echo 'host')"

  # Commit
  git commit -m "auto: snapshot $ts ($host)" >/dev/null || true

  # Push if upstream exists
  if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    git push >/dev/null || {
      echo "WARN: git push failed (network/remote?)" >&2
    }
  else
    if [[ "$warned_no_upstream" -eq 0 ]]; then
      warned_no_upstream=1
      echo "WARN: No upstream configured; skipping push. Set with: git push -u origin <branch>" >&2
    fi
  fi

  sleep "$interval_seconds"
done
