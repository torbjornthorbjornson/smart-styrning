#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_from_db.py (array-only, tolerant)
- Hämtar elpriser från DB
- Bygger rank-array (0..23)
- Hämtar alltid 23–25 timmar baserat på svensk tid
- Fyller ut saknade timmar med rank 23 (sämst)
- Pushar alltid komplett array till Arrigo
"""

import os, sys, json
import pymysql
import requests
from datetime import datetime, date, time, timedelta
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

# === Hämta priser från DB ===
def fetch_prices(which: str):
    today_local = date.today()
    if which == "tomorrow":
        day_local = today_local + timedelta(days=1)
    else:
        day_local = today_local

    # Svensk midnatt → nästa svensk midnatt, konverterat till UTC
    start_local = datetime.combine(day_local, time(0,0), tzinfo=TZ)
    end_local   = start_local + timedelta(days=1)
    start_utc   = start_local.astimezone(UTC).replace(tzinfo=None)
    end_utc     = end_local.astimezone(UTC).replace(tzinfo=None)

    log(f"📅 Hämtar priser för {which} ({day_local}) "
        f"UTC[{start_utc} → {end_utc})")

    conn = pymysql.connect(**read_db_config())
    rows = []
    with conn:
        with conn.cursor() as cur:
            sql = """
                SELECT datetime, price
                FROM electricity_prices
                WHERE datetime >= %s AND datetime < %s
                ORDER BY datetime
            """
            cur.execute(sql, (start_utc, end_utc))
            rows = cur.fetchall()

    log(f"📊 Hämtade {len(rows)} rader från DB för {which} ({day_local})")
    return rows, day_local

# === Bygg rank-array ===
def build_rank(rows, day_local):
    prices = [r["price"] for r in rows]
    if not prices:
        log(f"⚠️ Inga priser i databasen för {day_local}")
        return [23]*24

    # Gör 24h-array (svensk tid)
    rank = [None]*24
    for r in rows:
        hour_local = r["datetime"].replace(tzinfo=UTC).astimezone(TZ).hour
        rank[hour_local] = r["price"]

    # Omvandla till rank (lägsta pris = 0)
    filled = [p if p is not None else float("inf") for p in rank]
    sorted_hours = sorted(range(24), key=lambda h: filled[h])
    hour_to_rank = {h: i for i,h in enumerate(sorted_hours)}

    final = []
    missing = []
    for h in range(24):
        if rank[h] is None:
            final.append(23)  # sämst
            missing.append(h)
        else:
            final.append(hour_to_rank[h])

    if missing:
        log(f"⚠️ Saknade timmar {missing} för {day_local}, fyllde rank 23.")
    return final

# === Push till Arrigo ===
def push_to_arrigo(which, day_local, rank):
    url = os.getenv("ARRIGO_URL")
    token = os.getenv("ARRIGO_TOKEN")
    pvl = os.getenv("ARRIGO_PVL_PATH")

    if not url or not token or not pvl:
        log("❌ Saknar miljövariabler. Avbryter.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}
    mutation = """
    mutation Write($values: [VariableValueInput!]!) {
      writeData(values: $values)
    }
    """
    payload = {
        "query": mutation,
        "variables": {
            "values": [
                {"variableId": f"{pvl}:{i}", "value": str(val)}
                for i,val in enumerate(rank)
            ]
        }
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20, verify=True)
        resp.raise_for_status()
        data = resp.json()
        log(f"GraphQL svar: {json.dumps(data)}")
        log(f"✅ Push klar för {which} ({day_local})")
    except Exception as e:
        log(f"❌ FEL: {e}")
        sys.exit(1)

# === Huvudprogram ===
def main():
    which = os.getenv("RANK_WHEN", "today")
    rows, day_local = fetch_prices(which)
    rank = build_rank(rows, day_local)
    push_to_arrigo(which, day_local, rank)

if __name__ == "__main__":
    main()
