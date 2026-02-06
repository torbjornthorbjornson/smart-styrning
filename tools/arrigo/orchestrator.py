#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, time
from datetime import datetime, date, timedelta, time as dtime
import pytz
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
# Tidszoner (EXAKT SAMMA SOM RESTEN AV SYSTEMET)
# =========================
STHLM = pytz.timezone("Europe/Stockholm")
UTC   = pytz.UTC

def today_local_date():
    return datetime.now(UTC).astimezone(STHLM).date()

def local_day_to_utc_window(local_date: date):
    local_midnight = STHLM.localize(datetime.combine(local_date, dtime(0, 0)))
    utc_start = local_midnight.astimezone(UTC).replace(tzinfo=None)
    utc_end   = (local_midnight + timedelta(days=1)).astimezone(UTC).replace(tzinfo=None)
    return utc_start, utc_end

# =========================
# Arrigo / EXOL
# =========================
LOGIN_URL   = os.getenv("ARRIGO_LOGIN_URL")
GRAPHQL_URL = os.getenv("ARRIGO_GRAPHQL_URL")
USER        = os.getenv("ARRIGO_USER") or os.getenv("ARRIGO_USERNAME")
PASS        = os.getenv("ARRIGO_PASS") or os.getenv("ARRIGO_PASSWORD")

PVL_RAW = os.getenv("ARRIGO_PVL_B64") or os.getenv("ARRIGO_PVL_PATH")
if not PVL_RAW:
    raise SystemExit("Saknar ARRIGO_PVL_B64 eller ARRIGO_PVL_PATH")
PVL_B64 = ensure_b64(PVL_RAW)

VERIFY = build_verify()

TA_REQ = "Huvudcentral_C1.PI_PUSH_REQ"
TA_ACK = "Huvudcentral_C1.PI_PUSH_ACK"
TA_DAY = "Huvudcentral_C1.PI_PUSH_DAY"

Q_READ  = "query($p:String!){ data(path:$p){ variables{ technicalAddress value } } }"
M_WRITE = "mutation($v:[VariableKeyValue!]!){ writeData(variables:$v) }"

# =========================
# DB
# =========================
DB_NAME = "smart_styrning"
MYCNF   = "/home/runerova/.my.cnf"

SLEEP_SEC = 4

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

# =========================
# Arrigo helpers
# =========================
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
# DB → SVENSKT DYGN (FACIT)
# =========================
def db_fetch_prices_for_day(day_local: date):
    utc_start, utc_end = local_day_to_utc_window(day_local)

    conn = pymysql.connect(**read_db_config())
    with conn, conn.cursor() as cur:
        cur.execute("""
            SELECT datetime, price
            FROM electricity_prices
            WHERE datetime >= %s AND datetime < %s
            ORDER BY datetime
        """, (utc_start, utc_end))
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

        if req == 1 and ack == 0:
            base_day = today_local_date()
            target_day = base_day + timedelta(days=day)

            rows = db_fetch_prices_for_day(target_day)

            if len(rows) != 96:
                log(f"⏳ {target_day}: DB har {len(rows)}/96 → väntar")
                time.sleep(SLEEP_SEC)
                continue

            log(f"📤 Push dag {target_day}")

            rank, ec, ex, slot_price = build_rank_and_masks(rows)

            oat_yday = daily_avg_oat(target_day - timedelta(days=1))
            oat_tmr  = daily_avg_oat(target_day + timedelta(days=1))

            push_to_arrigo(
                rank, ec, ex,
                target_day,
                oat_yday,
                oat_tmr,
                slot_price
            )

            write_ta(token, idx, TA_ACK, 1)
            log("✅ PI_PUSH_ACK=1")

        time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    main()
