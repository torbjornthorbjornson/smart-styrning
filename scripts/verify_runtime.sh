#!/usr/bin/env bash
set -euo pipefail

# smartweb smoke test / runtime verification
# - import-test (Python)
# - HTTP routes on localhost
# - DB connection sanity (optional)

BASE_DIR="/home/runerova/smartweb"
URL_BASE="${SMARTWEB_URL_BASE:-http://127.0.0.1:8000}"

# Prefer the same venv as gunicorn uses.
PY="${SMARTWEB_PYTHON:-/home/runerova/myenv/bin/python3}"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

CURL_BIN="${SMARTWEB_CURL:-curl}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

step() {
  echo "==> $*"
}

step "Python import app"
cd "$BASE_DIR"
"$PY" -c "import app; print('OK import app')" || fail "import app"

step "HTTP smoke"
if command -v "$CURL_BIN" >/dev/null 2>&1; then
  "$CURL_BIN" -fsS "$URL_BASE/" >/dev/null || fail "GET /"
  "$CURL_BIN" -fsS "$URL_BASE/styrning" >/dev/null || fail "GET /styrning"
  "$CURL_BIN" -fsS "$URL_BASE/elprisvader" >/dev/null || fail "GET /elprisvader"
  # /exo kan vara skyddad av Basic Auth; behandla 200/401 som OK.
  code=$("$CURL_BIN" -sS -o /dev/null -w "%{http_code}" "$URL_BASE/exo" || echo "000")
  if [[ "$code" != "200" && "$code" != "401" ]]; then
    fail "GET /exo (expected 200 or 401, got $code)"
  fi
else
  step "curl saknas, hoppar HTTP-test"
fi

step "DB sanity (optional)"
# This uses smartweb_backend DB connection which reads /home/runerova/.my.cnf.
# If pymysql isn't available in the chosen Python, we skip.
"$PY" - <<'PY'
import sys

try:
    import pymysql  # noqa: F401
except Exception as e:
    print(f"SKIP DB sanity (pymysql missing): {e.__class__.__name__}: {e}")
    sys.exit(0)

try:
    from smartweb_backend.db.connection import get_connection

    con = get_connection()
    with con.cursor() as cur:
        cur.execute("SELECT 1")
        row = cur.fetchone()
    con.close()
    if not row:
        raise RuntimeError("Empty result")
    print("OK DB SELECT 1")
except Exception as e:
    print(f"FAIL DB sanity: {e.__class__.__name__}: {e}")
    sys.exit(2)
PY

step "DONE"
echo "OK: smartweb runtime smoke test passed"
