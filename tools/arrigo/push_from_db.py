#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_from_db.py (modern, robust)
- Hämtar elpriser från DB (UTC)
- Bygger rank-array (0..23)
- Räknar ut masker + stämpel
- Loggar in mot Arrigo → authToken
- Pushar till Arrigo via index-nycklar
"""

import os, sys, json, re
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
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{now} {msg}\n")
    print(msg)

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

def arrigo_login(login_url, user, password, verify_tls=True):
    r = requests.post(login_url, json={"username": user, "password": password}, timeout=15, verify=verify_tls)
    r.raise_for_status()
    tok = r.json().get("authToken")
    if not tok:
        raise SystemExit("Inget authToken i login-svar")
    return tok

def gql(url, token, query, variables, verify_tls=True):
    r = requests.post(url,
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "variables": variables},
        timeout=20, verify=verify_tls)
    if r.status_code >= 400:
        raise SystemExit(f"GraphQL HTTP {r.status_code}: {r.text[:500]}")
    j = r.json()
    if "errors" in j:
        raise SystemExit("GraphQL-fel: " + json.dumps(j["errors"], ensure_ascii=False))
    return j["data"]

# === Hämta priser från DB ===
def fetch_prices(which: str):
    today_local = date.today()
    if which == "tomorrow":
        day_local = today_local + timedelta(days=1)
    else:
        day_local = today_local

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
    prices = [r["price"] for r in rows]
    if not prices:
        log(f"⚠️ Inga priser i DB för {day_local}")
        return [23]*24

    hourly = [None]*24
    for r in rows:
        h = r["datetime"].replace(tzinfo=UTC).astimezone(TZ).hour
        hourly[h] = r["price"]

    filled = [p if p is not None else float("inf") for p in hourly]
    sorted_hours = sorted(range(24), key=lambda h: filled[h])
    hour_to_rank = {h: i for i,h in enumerate(sorted_hours)}

    final = []
    for h in range(24):
        if hourly[h] is None:
            final.append(23)
        else:
            final.append(hour_to_rank[h])
    return final

# === Packa masker ===
def pack_mask(hours):
    bits = 0
    for h in hours:
        if 0 <= h <= 23: bits |= (1 << h)
    return bits & 0xFFFF, (bits >> 16) & 0xFFFF

# === Push till Arrigo ===
def push_to_arrigo(rank, day_local):
    login_url   = os.environ["ARRIGO_LOGIN_URL"]
    graphql_url = os.environ["ARRIGO_GRAPHQL_URL"]
    user        = os.environ["ARRIGO_USER"]
    password    = os.environ["ARRIGO_PASS"]
    pvl_path    = os.environ["ARRIGO_PVL_PATH"]
    verify_tls  = os.environ.get("ARRIGO_INSECURE","0") != "1"

    token = arrigo_login(login_url, user, password, verify_tls)

    # Hämta PVL-lista → index-map
    data = gql(graphql_url, token,
        'query ($path:String!){ data(path:$path){ variables{ technicalAddress } } }',
        {"path": pvl_path}, verify_tls)

    vars_list = (data.get("data") or {}).get("variables") or []
    ta_index = { (v.get("technicalAddress") or "").strip(): i for i,v in enumerate(vars_list)}

    writes = []
    # Rank-array
    for hour,val in enumerate(rank):
        writes.append({"key": f"{pvl_path}:{hour}", "value": str(val)})

    # Stamp
    if any("PRICE_STAMP" in ta for ta in ta_index):
        stamp = int(day_local.strftime("%Y%m%d"))
        idx = [i for ta,i in ta_index.items() if ta.endswith(".PRICE_STAMP")][0]
        writes.append({"key": f"{pvl_path}:{idx}", "value": str(stamp)})

    # Skicka mutation
    mutation = "mutation ($variables:[VariableKeyValue!]!){ writeData(variables:$variables) }"
    gql(graphql_url, token, mutation, {"variables": writes}, verify_tls)
    log(f"✅ Push klar för {day_local}, {len(writes)} variabler")

# === Huvud ===
def main():
    which = os.getenv("RANK_WHEN","today")
    rows, day_local = fetch_prices(which)
    rank = build_rank(rows, day_local)
    push_to_arrigo(rank, day_local)

if __name__ == "__main__":
    main()
