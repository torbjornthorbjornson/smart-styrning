#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, time, json
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from configparser import ConfigParser

import requests
import pymysql

from push_from_db import (
    fetch_prices,
    build_rank_and_masks,
    daily_avg_oat,
    push_to_arrigo,
    ensure_b64,
    build_verify,
)

TZ  = ZoneInfo("Europe/Stockholm")
UTC = ZoneInfo("UTC")

LOGIN_URL   = os.getenv("ARRIGO_LOGIN_URL")
GRAPHQL_URL = os.getenv("ARRIGO_GRAPHQL_URL")
USER        = os.getenv("ARRIGO_USER") or os.getenv("ARRIGO_USERNAME")
PASS        = os.getenv("ARRIGO_PASS") or os.getenv("ARRIGO_PASSWORD")

PVL_RAW = os.getenv("ARRIGO_PVL_B64") or os.getenv("ARRIGO_PVL_PATH")
if not PVL_RAW:
    raise SystemExit("Saknar ARRIGO_PVL_B64 eller ARRIGO_PVL_PATH")
PVL_B64 = ensure_b64(PVL_RAW)

VERIFY = build_verify()

TA_REQ      = "Huvudcentral_C1.PI_PUSH_REQ"
TA_ACK      = "Huvudcentral_C1.PI_PUSH_ACK"
TA_DAY      = "Huvudcentral_C1.PI_PUSH_DAY"
TA_TD_READY = "Huvudcentral_C1.TD_READY"
TA_TM_READY = "Huvudcentral_C1.TM_READY"

DB_NAME = "smart_styrning"
MYCNF   = "/home/runerova/.my.cnf"

SLEEP_OK_SEC  = 10
ACK_PULSE_SEC = 2.0

class TransientAPIError(Exception):
    pass

def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)

def to_int(x, d=0):
    try:
        return int(float(x))
    except Exception:
        return d

def arrigo_login():
    r = requests.post(
        LOGIN_URL,
        json={"username": USER, "password": PASS},
        timeout=20,
        verify=VERIFY,
    )
    r.raise_for_status()
    return r.json()["authToken"]

def gql(token, query, variables):
    r = requests.post(
        GRAPHQL_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "variables": variables},
        timeout=30,
        verify=VERIFY,
    )
    r.raise_for_status()
    return r.json()

Q_READ  = "query($p:String!){ data(path:$p){ variables{technicalAddress value} } }"
M_WRITE = "mutation($v:[VariableKeyValue!]!){ writeData(variables:$v) }"

def read_vals_and_idx(token):
    j = gql(token, Q_READ, {"p": PVL_B64})
    vars_list = j["data"]["data"]["variables"]
    vals, idx = {}, {}
    for i, v in enumerate(vars_list):
        ta = v["technicalAddress"]
        vals[ta] = v["value"]
        idx[ta] = i
    return vals, idx

def write_ta(token, idx, ta, val):
    key = f"{PVL_B64}:{idx[ta]}"
    gql(token, M_WRITE, {"v": [{"key": key, "value": str(val)}]})

class PulseState:
    def __init__(self):
        self.ack_at = None

def handle_price_handshake(token, vals, idx, ps):
    req = to_int(vals.get(TA_REQ))
    ack = to_int(vals.get(TA_ACK))
    day = to_int(vals.get(TA_DAY))
    td  = to_int(vals.get(TA_TD_READY))
    tm  = to_int(vals.get(TA_TM_READY))

    if req == 1 and ack == 0:
        which = "today" if day == 0 else "tomorrow"

        if (which == "today" and td == 1) or (which == "tomorrow" and tm == 1):
            log("ℹ️ READY=1 → ACK + REQ=0")
            write_ta(token, idx, TA_ACK, 1)
            write_ta(token, idx, TA_REQ, 0)
            ps.ack_at = time.monotonic()
            return

        rows, day_local = fetch_prices(which)
        if which == "tomorrow" and len(rows) < 96:
            return

        rank, ec, ex, slot = build_rank_and_masks(rows)
        today = date.today()
        push_to_arrigo(
            rank, ec, ex, day_local,
            daily_avg_oat(today - timedelta(days=1)),
            daily_avg_oat(today + timedelta(days=1)),
            slot
        )

        log("📤 Push klar → ACK + REQ=0")
        write_ta(token, idx, TA_ACK, 1)
        write_ta(token, idx, TA_REQ, 0)
        ps.ack_at = time.monotonic()

    if ack == 1 and ps.ack_at and (time.monotonic() - ps.ack_at) > ACK_PULSE_SEC:
        write_ta(token, idx, TA_ACK, 0)
        ps.ack_at = None

def main():
    token = arrigo_login()
    ps = PulseState()
    log("🔌 Orchestrator start")

    while True:
        vals, idx = read_vals_and_idx(token)
        handle_price_handshake(token, vals, idx, ps)
        time.sleep(SLEEP_OK_SEC)

if __name__ == "__main__":
    main()
