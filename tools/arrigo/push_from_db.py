#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_from_db.py (robust, index-baserad)
- Hämtar elpriser från DB (UTC) och bygger rank 0..23
- Loggar in mot Arrigo
- Läser PVL-variabellistan, bygger TA→index
- Skriver PRICE_RANK(h), PRICE_STAMP och togglar PRICE_OK
- Skriver även:
  * OAT_mean_yday (gårdagens svenska dygn)
  * OAT_mean_tomorrow (morgondagens svenska dygn)
  * EC/EX-maskar (extreme cheap/expensive)
"""

import os, re, json, base64
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
    s = path_or_b64.strip()
    is_b64_chars = re.fullmatch(r'[A-Za-z0-9+/=]+', s or '') is not None
    if is_b64_chars and len(s) % 4 == 0:
        try:
            base64.b64decode(s)
            return s
        except Exception:
            pass
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

# === DB-funktioner ===
def fetch_prices(which: str):
    today_local = date.today()
    day_local = today_local + timedelta(days=1) if which == "tomorrow" else today_local
    start_local = datetime.combine(day_local, time(0,0), tzinfo=TZ)
    end_local   = start_local + timedelta(days=1)
    start_utc   = start_local.astimezone(UTC).replace(tzinfo=None)
    end_utc     = end_local.astimezone(UTC).replace(tzinfo=None)

    log(f"📅 Hämtar elpriser för {which} (lokalt {day_local}) → UTC[{start_utc} → {end_utc})")

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

def build_rank(rows, day_local):
    if not rows:
        log(f"⚠️ Inga priser i DB för {day_local}, fyller med rank=23")
        return [23]*24

    hourly = [None]*24
    for r in rows:
        h = r["datetime"].replace(tzinfo=UTC).astimezone(TZ).hour
        hourly[h] = r["price"]

    filled = [p if p is not None else float("inf") for p in hourly]
    sorted_hours = sorted(range(24), key=lambda h: filled[h])
    hour_to_rank = {h: i for i,h in enumerate(sorted_hours)}
    return [ (23 if hourly[h] is None else hour_to_rank[h]) for h in range(24) ]

def daily_avg_oat_local(day_local: date):
    start_local = datetime.combine(day_local, time(0, 0), tzinfo=TZ)
    end_local   = start_local + timedelta(days=1)
    start_utc   = start_local.astimezone(UTC).replace(tzinfo=None)
    end_utc     = end_local.astimezone(UTC).replace(tzinfo=None)

    log(f"🌍 OAT fönster lokalt {start_local}→{end_local} | UTC {start_utc}→{end_utc}")

    conn = pymysql.connect(**read_db_config())
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT AVG(temperature) AS avgtemp
                FROM weather
                WHERE timestamp >= %s AND timestamp < %s
            """, (start_utc, end_utc))
            row = cur.fetchone()

    if not row or row["avgtemp"] is None:
        return None
    return round(float(row["avgtemp"]), 1)

def fetch_masks_for_day(day_local: date):
    site = os.getenv("ARRIGO_SITE_CODE", "C1")
    conn = pymysql.connect(**read_db_config())
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT mask_ec_L, mask_ec_H, mask_ex_L, mask_ex_H
                FROM exo_day_summary
                WHERE site_code=%s AND day_local=%s
                ORDER BY id DESC
                LIMIT 1
            """, (site, day_local))
            row = cur.fetchone()
    if not row:
        return None
    return {
        "EC_MASK_L": int(row["mask_ec_L"]),
        "EC_MASK_H": int(row["mask_ec_H"]),
        "EX_MASK_L": int(row["mask_ex_L"]),
        "EX_MASK_H": int(row["mask_ex_H"]),
    }

# === Push ===
def push_to_arrigo(rank, day_local):
    login_url   = getenv_any(["ARRIGO_LOGIN_URL"], required=True)
    graphql_url = getenv_any(["ARRIGO_GRAPHQL_URL"], required=True)
    user        = getenv_any(["ARRIGO_USER","ARRIGO_USERNAME"], required=True)
    password    = getenv_any(["ARRIGO_PASS","ARRIGO_PASSWORD"], required=True)
    pvl_raw     = getenv_any(["ARRIGO_PVL_B64","ARRIGO_PVL_PATH"], required=True)
    pvl_b64     = ensure_b64(pvl_raw)
    verify      = build_verify()

    token = arrigo_login(login_url, user, password, verify)

    data = gql(graphql_url, token,
        'query ($path:String!){ data(path:$path){ variables{ technicalAddress } } }',
        {"path": pvl_b64}, verify)
    vars_list = (data.get("data") or {}).get("variables") or []

    rank_idx = {}
    idx_price_ok = idx_stamp = None
    idx_oat_yday = idx_oat_tmr = None
    idx_ec_L = idx_ec_H = idx_ex_L = idx_ex_H = None

    for i, v in enumerate(vars_list):
        ta = (v.get("technicalAddress") or "").strip()
        if not ta: continue
        m = re.search(r'\.PRICE_RANK\((\d+)\)$', ta)
        if m: rank_idx[int(m.group(1))] = i; continue
        if ta.endswith(".PRICE_OK"): idx_price_ok = i; continue
        if ta.endswith(".PRICE_STAMP"): idx_stamp = i; continue
        if ta.endswith(".OAT_mean_yday"): idx_oat_yday = i; continue
        if ta.endswith(".OAT_mean_tomorrow"): idx_oat_tmr = i; continue
        if ta.endswith(".EC_MASK_L"): idx_ec_L = i; continue
        if ta.endswith(".EC_MASK_H"): idx_ec_H = i; continue
        if ta.endswith(".EX_MASK_L"): idx_ex_L = i; continue
        if ta.endswith(".EX_MASK_H"): idx_ex_H = i; continue

    # Gate av
    if idx_price_ok is not None:
        gql(graphql_url, token,
            "mutation ($variables:[VariableKeyValue!]!){ writeData(variables:$variables) }",
            {"variables": [{"key": f"{pvl_b64}:{idx_price_ok}", "value": "0"}]}, verify)
        log("🔒 PRICE_OK=0 (gate av)")

    writes = []
    missing = []

    for h in range(24):
        idx = rank_idx.get(h)
        if idx is None: missing.append(h); continue
        writes.append({"key": f"{pvl_b64}:{idx}", "value": str(rank[h])})

    if idx_stamp is not None:
        stamp = int(day_local.strftime("%Y%m%d"))
        writes.append({"key": f"{pvl_b64}:{idx_stamp}", "value": str(stamp)})

    today_local = date.today()
    oat_yday = daily_avg_oat_local(today_local - timedelta(days=1))
    oat_tmr  = daily_avg_oat_local(today_local + timedelta(days=1))

    if idx_oat_yday is not None and oat_yday is not None:
        writes.append({"key": f"{pvl_b64}:{idx_oat_yday}", "value": f"{oat_yday}"})
        log(f"🌡️ OAT_mean_yday = {oat_yday} °C")
    if idx_oat_tmr is not None and oat_tmr is not None:
        writes.append({"key": f"{pvl_b64}:{idx_oat_tmr}", "value": f"{oat_tmr}"})
        log(f"🌡️ OAT_mean_tomorrow = {oat_tmr} °C")

    masks = fetch_masks_for_day(day_local)
    if masks:
        if idx_ec_L is not None: writes.append({"key": f"{pvl_b64}:{idx_ec_L}", "value": str(masks["EC_MASK_L"])})
        if idx_ec_H is not None: writes.append({"key": f"{pvl_b64}:{idx_ec_H}", "value": str(masks["EC_MASK_H"])})
        if idx_ex_L is not None: writes.append({"key": f"{pvl_b64}:{idx_ex_L}", "value": str(masks["EX_MASK_L"])})
        if idx_ex_H is not None: writes.append({"key": f"{pvl_b64}:{idx_ex_H}", "value": str(masks["EX_MASK_H"])})
        log(f"🧩 Masks för {day_local}: {masks}")
    else:
        log(f"⚠️ Inga maskar i exo_day_summary för {day_local}")

    if missing:
        log(f"⚠️ Saknar index för PRICE_RANK timmar: {missing}")

    if not writes:
        raise SystemExit("Inget att skriva")

    gql(graphql_url, token,
        "mutation ($variables:[VariableKeyValue!]!){ writeData(variables:$variables) }",
        {"variables": writes}, verify)
    log(f"✅ Skrev {len(writes)} variabler")

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
