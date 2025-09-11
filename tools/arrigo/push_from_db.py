#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_from_db.py (robust, index-baserad)
- Hämtar elpriser från DB (UTC) och bygger rank 0..23
- Loggar in mot Arrigo
- Läser PVL-variabellistan, bygger TA→index
- Skriver PRICE_RANK(h), PRICE_STAMP och togglar PRICE_OK
- Miljövariabler (stöd för flera namn):
  ARRIGO_LOGIN_URL
  ARRIGO_GRAPHQL_URL
  ARRIGO_USER | ARRIGO_USERNAME
  ARRIGO_PASS | ARRIGO_PASSWORD
  ARRIGO_PVL_B64 | ARRIGO_PVL_PATH   (klartext auto-B64)
  ARRIGO_INSECURE=1 (valfritt)
  REQUESTS_CA_BUNDLE=/path/to/ca.crt (valfritt)
"""

import os, sys, json, re, base64
from datetime import datetime, date, time, timedelta
import pymysql, requests
from zoneinfo import ZoneInfo
from configparser import ConfigParser

# === Konstanter ===
TZ = ZoneInfo("Europe/Stockholm")
UTC = ZoneInfo("UTC")
LOG_PATH = "/home/runerova/smartweb/tools/arrigo/logs/arrigo_push.log"

# === Hjälpfunktioner ===
def log(msg):
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{now} {msg}\n")
    except Exception:
        pass
    print(msg, flush=True)

def read_db_config():
    cfg = ConfigParser()
    cfg.read("/home/runerova/.my.cnf")
    return {
        "host": "localhost",
        "user": cfg["client"]["user"],
        "password": cfg["client"]["password"],
        "database": "smart_styrning",
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }

def getenv_any(names, required=False):
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    if required:
        raise KeyError(f"Saknar någon av miljövariablerna: {', '.join(names)}")
    return None

def ensure_b64(path_or_b64: str) -> str:
    # Om strängen ser ut som Base64 (A-Za-z0-9+/= och längd%4==0), anta att den redan är B64.
    s = path_or_b64.strip()
    is_b64_chars = re.fullmatch(r'[A-Za-z0-9+/=]+', s or '') is not None
    if is_b64_chars and len(s) % 4 == 0:
        try:
            base64.b64decode(s)
            return s
        except Exception:
            pass
    # Annars B64-enkoda klartext
    return base64.b64encode(s.encode("utf-8")).decode("ascii")

def build_verify():
    if os.environ.get("ARRIGO_INSECURE", "0") == "1":
        return False
    cab = os.environ.get("REQUESTS_CA_BUNDLE")
    return cab if cab else True

def arrigo_login(login_url, user, password, verify):
    r = requests.post(login_url, json={"username": user, "password": password}, timeout=20, verify=verify)
    r.raise_for_status()
    tok = r.json().get("authToken")
    if not tok:
        raise SystemExit("Inget authToken i login-svar")
    return tok

def gql(url, token, query, variables, verify):
    r = requests.post(url,
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "variables": variables},
        timeout=30, verify=verify)
    if r.status_code >= 400:
        raise SystemExit(f"GraphQL HTTP {r.status_code}: {r.text[:500]}")
    j = r.json()
    if "errors" in j:
        raise SystemExit("GraphQL-fel: " + json.dumps(j["errors"], ensure_ascii=False))
    return j["data"]

# === Hämta priser från DB ===
def fetch_prices(which: str):
    today_local = date.today()
    day_local = today_local + timedelta(days=1) if which == "tomorrow" else today_local
    start_local = datetime.combine(day_local, time(0,0), tzinfo=TZ)
    end_local   = start_local + timedelta(days=1)
    start_utc   = start_local.astimezone(UTC).replace(tzinfo=None)
    end_utc     = end_local.astimezone(UTC).replace(tzinfo=None)

    log(f"📅 Hämtar priser för {which} ({day_local}) UTC[{start_utc} → {end_utc})")

    conn = pymysql.connect(**read_db_config())
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT datetime, price
                FROM electricity_prices
                WHERE datetime >= %s AND datetime < %s
                ORDER BY datetime
            """, (start_utc, end_utc))
            rows = cur.fetchall()

    log(f"📊 Hämtade {len(rows)} rader från DB för {which} ({day_local})")
    return rows, day_local

# === Bygg rank-array (0..23) ===
def build_rank(rows, day_local):
    if not rows:
        log(f"⚠️ Inga priser i DB för {day_local}, fyller med rank=23")
        return [23]*24

    hourly = [None]*24
    for r in rows:
        h = r["datetime"].replace(tzinfo=UTC).astimezone(TZ).hour
        hourly[h] = r["price"]

    # Rank: saknade timmar blir sämst (∞)
    filled = [p if p is not None else float("inf") for p in hourly]
    sorted_hours = sorted(range(24), key=lambda h: filled[h])
    hour_to_rank = {h: i for i,h in enumerate(sorted_hours)}
    return [ (23 if hourly[h] is None else hour_to_rank[h]) for h in range(24) ]

# === Push till Arrigo (index-baserad) ===
def push_to_arrigo(rank, day_local):
    login_url   = getenv_any(["ARRIGO_LOGIN_URL"], required=True)
    graphql_url = getenv_any(["ARRIGO_GRAPHQL_URL"], required=True)
    user        = getenv_any(["ARRIGO_USER","ARRIGO_USERNAME"], required=True)
    password    = getenv_any(["ARRIGO_PASS","ARRIGO_PASSWORD"], required=True)
    pvl_raw     = getenv_any(["ARRIGO_PVL_B64","ARRIGO_PVL_PATH"], required=True)
    pvl_b64     = ensure_b64(pvl_raw)
    verify      = build_verify()

    token = arrigo_login(login_url, user, password, verify)

    # Hämta PVL-lista → TA→index
    data = gql(graphql_url, token,
        'query ($path:String!){ data(path:$path){ variables{ technicalAddress } } }',
        {"path": pvl_b64}, verify)
    vars_list = (data.get("data") or {}).get("variables") or []

    ta_index = {}
    rank_idx = {}
    idx_price_ok = None
    idx_stamp = None

    for i, v in enumerate(vars_list):
        ta = (v.get("technicalAddress") or "").strip()
        ta_index[ta] = i
        m = re.search(r'\.PRICE_RANK\((\d+)\)$', ta)
        if m:
            rank_idx[int(m.group(1))] = i
        elif ta.endswith(".PRICE_OK"):
            idx_price_ok = i
        elif ta.endswith(".PRICE_STAMP"):
            idx_stamp = i

    # Säkerhetsgate av (PRICE_OK=0) om den finns
    if idx_price_ok is not None:
        gql(graphql_url, token,
            "mutation ($variables:[VariableKeyValue!]!){ writeData(variables:$variables) }",
            {"variables": [{"key": f"{pvl_b64}:{idx_price_ok}", "value": "0"}]}, verify)
        log("🔒 PRICE_OK=0 (gate av)")

    writes = []
    # Rank-array med rätt index
    missing = []
    for h in range(24):
        idx = rank_idx.get(h)
        if idx is None:
            missing.append(h)
            continue
        writes.append({"key": f"{pvl_b64}:{idx}", "value": str(rank[h])})

    # Stamp YYYYMMDD om finns
    if idx_stamp is not None:
        stamp = int(day_local.strftime("%Y%m%d"))
        writes.append({"key": f"{pvl_b64}:{idx_stamp}", "value": str(stamp)})

    if missing:
        log(f"⚠️ Saknar index för PRICE_RANK timmar: {missing}")

    if not writes:
        raise SystemExit("Inget att skriva — kontrollera PVL och variabelnamn i Arrigo.")

    # Batch-skriv
    gql(graphql_url, token,
        "mutation ($variables:[VariableKeyValue!]!){ writeData(variables:$variables) }",
        {"variables": writes}, verify)
    log(f"✅ Skrev {len(writes)} variabler (rank + ev. stamp)")

    # Gate på igen (PRICE_OK=1) om den finns
    if idx_price_ok is not None:
        gql(graphql_url, token,
            "mutation ($variables:[VariableKeyValue!]!){ writeData(variables:$variables) }",
            {"variables": [{"key": f"{pvl_b64}:{idx_price_ok}", "value": "1"}]}, verify)
        log("🔓 PRICE_OK=1 (gate på)")

    log(f"🏁 Push klar för {day_local}")

# === Huvud ===
def main():
    which = os.getenv("RANK_WHEN","today")
    rows, day_local = fetch_prices(which)
    rank = build_rank(rows, day_local)
    push_to_arrigo(rank, day_local)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"💥 Fel: {e}")
        raise
