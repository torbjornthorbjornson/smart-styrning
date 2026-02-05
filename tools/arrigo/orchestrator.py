#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, time
from datetime import datetime, date, timedelta, time as dtime
from zoneinfo import ZoneInfo
import pymysql
import requests
from configparser import ConfigParser

from push_from_db import (
    build_rank_and_masks,
    daily_avg_oat,
    push_to_arrigo,
    ensure_b64,
    build_verify,
)

# =========================
# Tidszoner
# =========================
TZ  = ZoneInfo("Europe/Stockholm")
UTC = ZoneInfo("UTC")

# =========================
# Arrigo / EXOL
# =========================
LOGIN_URL   = os.getenv("ARRIGO_LOGIN_URL")
GRAPHQL_URL = os.getenv("ARRIGO_GRAPHQL_URL")
USER        = os.getenv("ARRIGO_USER") or os.getenv("ARRIGO_USERNAME")
PASS        = os.getenv("ARRIGO_PASS") or os.getenv("ARRIGO_PASSWORD")

PVL_RAW = os.getenv("ARRIGO_PVL_B64") or os.getenv("ARRIGO_PVL_PATH")
PVL_B64 = ensure_b64(PVL_RAW)

VERIFY = build_verify()

TA_REQ      = "Huvudcentral_C1.PI_PUSH_REQ"
TA_ACK      = "Huvudcentral_C1.PI_PUSH_ACK"
TA_DAY      = "Huvudcentral_C1.PI_PUSH_DAY"
TA_TD_READY = "Huvudcentral_C1.TD_READY"
TA_TM_READY = "Huvudcentral_C1.TM_READY"

Q_READ  = "query($p:String!){ data(path:$p){ variables{ technicalAddress value } } }"
M_WRITE = "mutation($v:[VariableKeyValue!]!){ writeData(variables:$v) }"

# =========================
# DB
# =========================
DB_NAME = "smart_styrning"
MYCNF   = "/home/runerova/.my.cnf"

# =========================
# Loop
# =========================
SLEEP_SEC = 4

# =========================
# Helpers
# =========================
def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)

def to_int(x, d=0):
    try:
        return int(float(x))
    except Exception:
        return d

def read_db_config():
    cfg = ConfigParser()
    cfg.read(MYCNF)
    return dict(
        host="localhost",
        user=cfg["client"]["user"],
        password=cfg["client"]["password"],
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

def arrigo_login():
    r = requests.post(
        LOGIN_URL,
        json={"username": USER, "password": PASS},
        timeout=20,
        verify=VERIFY,
    )
    r.raise_for_status()
    tok = r.json().get("authToken")
    if not tok:
        raise SystemExit("Login utan token")
    return tok

def gql(token, query, variables):
    r = requests.post(
        GRAPHQL_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "variables": variables},
        timeout=30,
        verify=VERIFY,
    )
    r.raise_for_status()
    j = r.json()
    if "errors" in j:
        raise RuntimeError(j["errors"])
    return j["data"]

def read_vals_and_idx(token):
    data = gql(token, Q_READ, {"p": PVL_B64})
    vars_list = data["data"]["variables"]
    vals, idx = {}, {}
    for i, v in enumerate(vars_list):
        ta = v["technicalAddress"]
        vals[ta] = v.get("value")
        idx[ta] = i
    return vals, idx

def write_ta(token, idx, ta, val):
    key = f"{PVL_B64}:{idx[ta]}"
    gql(token, M_WRITE, {"v": [{"key": key, "value": str(val)}]})

# =========================
# Prislogik (EXAKT som spotpris.py)
# =========================
def db_fetch_prices_for_day(day_local: date):
    start_local = datetime.combine(day_local, dtime(0,0), tzinfo=TZ)
    end_local   = start_local + timedelta(days=1)

    start_utc = start_local.astimezone(UTC).replace(tzinfo=None)
    end_utc   = end_local.astimezone(UTC).replace(tzinfo=None)

    conn = pymysql.connect(**read_db_config())
    with conn, conn.cursor() as cur:
        cur.execute("""
            SELECT datetime, price
            FROM electricity_prices
            WHERE datetime >= %s AND datetime < %s
            ORDER BY datetime
        """, (start_utc, end_utc))
        rows = cur.fetchall()

    return rows

# =========================
# Main
# =========================
def main():
    token = arrigo_login()
    log("🔌 Orchestrator (PRICE ONLY) startad")

    while True:
        try:
            vals, idx = read_vals_and_idx(token)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                log("🔑 401 → relogin")
                token = arrigo_login()
                time.sleep(2)
                continue
            raise

        req = to_int(vals.get(TA_REQ))
        ack = to_int(vals.get(TA_ACK))
        day = to_int(vals.get(TA_DAY))

        log(f"REQ={req} DAY={day} ACK={ack}")

        # Endast svara när EXOL begär
        if req == 1 and ack == 0:
            which = "today" if day == 0 else "tomorrow"
            day_local = datetime.now(TZ).date()
            if which == "tomorrow":
                day_local += timedelta(days=1)

            rows = db_fetch_prices_for_day(day_local)

            if len(rows) != 96:
                log(f"⏳ {which}: DB har {len(rows)}/96 → väntar")
                time.sleep(SLEEP_SEC)
                continue

            log(f"📤 Push {which} ({day_local})")

            rank, ec, ex, slot_price = build_rank_and_masks(rows)

            today = datetime.now(TZ).date()
            oat_yday = daily_avg_oat(today - timedelta(days=1))
            oat_tmr  = daily_avg_oat(today + timedelta(days=1))

            push_to_arrigo(
                rank, ec, ex,
                day_local,
                oat_yday,
                oat_tmr,
                slot_price
            )

            write_ta(token, idx, TA_ACK, 1)
            log("✅ PI_PUSH_ACK=1")

        time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    main()
