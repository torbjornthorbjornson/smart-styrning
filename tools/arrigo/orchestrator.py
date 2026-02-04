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

VERIFY  = build_verify()

TA_REQ      = "Huvudcentral_C1.PI_PUSH_REQ"
TA_ACK      = "Huvudcentral_C1.PI_PUSH_ACK"
TA_DAY      = "Huvudcentral_C1.PI_PUSH_DAY"
TA_TD_READY = "Huvudcentral_C1.TD_READY"
TA_TM_READY = "Huvudcentral_C1.TM_READY"

TA_VV_CHANGED   = "Huvudcentral_C1.VV_PLAN_CHANGED"
TA_VV_ACK       = "Huvudcentral_C1.VV_PLAN_ACK"
TA_HEAT_CHANGED = "Huvudcentral_C1.HEAT_PLAN_CHANGED"
TA_HEAT_ACK     = "Huvudcentral_C1.HEAT_PLAN_ACK"

BASE_VV   = "Huvudcentral_C1.VV_PLAN"
BASE_HEAT = "Huvudcentral_C1.HEAT_PLAN"
N = 96

Q_READ = """query($p:String!){
  data(path:$p){
    variables{ technicalAddress value }
  }
}"""
M_WRITE = "mutation($v:[VariableKeyValue!]!){ writeData(variables:$v) }"

DB_NAME   = "smart_styrning"
MYCNF     = "/home/runerova/.my.cnf"
SITE_CODE = os.getenv("SITE_CODE", "HALTORP244")


class TransientAPIError(Exception):
    pass


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)

def to_int(x, default=0):
    try:
        return int(float(x))
    except Exception:
        return default

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
        autocommit=True,
    )

def ensure_db_tables():
    con = pymysql.connect(**read_db_config())
    try:
        with con.cursor() as cur:
            cur.execute("""
              CREATE TABLE IF NOT EXISTS arrigo_plan_cache (
                site_code VARCHAR(64) NOT NULL,
                plan_type VARCHAR(32) NOT NULL,
                day_local DATE NOT NULL,
                fetched_at DATETIME NOT NULL,
                periods LONGTEXT NOT NULL,
                PRIMARY KEY (site_code, plan_type, day_local)
              ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
    finally:
        con.close()

def db_upsert_plan(plan_type: str, day_local, periods):
    fetched_at = datetime.now(UTC).replace(tzinfo=None)
    con = pymysql.connect(**read_db_config())
    try:
        with con.cursor() as cur:
            cur.execute("""
              INSERT INTO arrigo_plan_cache (site_code, plan_type, day_local, fetched_at, periods)
              VALUES (%s,%s,%s,%s,%s)
              ON DUPLICATE KEY UPDATE
                fetched_at = VALUES(fetched_at),
                periods    = VALUES(periods)
            """, (SITE_CODE, plan_type, day_local, fetched_at, json.dumps(periods)))
    finally:
        con.close()
    ones = sum(1 for x in periods if int(x) == 1)
    return ones, fetched_at

def arrigo_login():
    if not LOGIN_URL or not USER or not PASS:
        raise SystemExit("Saknar ARRIGO_LOGIN_URL / ARRIGO_USER / ARRIGO_PASS")
    r = requests.post(LOGIN_URL, json={"username": USER, "password": PASS}, timeout=20, verify=VERIFY)
    r.raise_for_status()
    tok = r.json().get("authToken")
    if not tok:
        raise SystemExit("Inget authToken i login-svar")
    return tok

def gql(token, query, variables):
    if not GRAPHQL_URL:
        raise SystemExit("Saknar ARRIGO_GRAPHQL_URL")

    try:
        r = requests.post(
            GRAPHQL_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"query": query, "variables": variables},
            timeout=30,
            verify=VERIFY,
        )

        # Transienta fel (Arrigo/Reverse proxy)
        if r.status_code in (429, 502, 503, 504):
            raise TransientAPIError(f"{r.status_code} {r.reason}")

        r.raise_for_status()

        j = r.json()
        if "errors" in j:
            raise RuntimeError("GraphQL-fel: " + str(j["errors"]))
        return j

    except requests.exceptions.Timeout as e:
        raise TransientAPIError(f"timeout: {e}") from e
    except requests.exceptions.ConnectionError as e:
        raise TransientAPIError(f"connection: {e}") from e

def read_vals_and_idx(token):
    j = gql(token, Q_READ, {"p": PVL_B64})
    data = j.get("data") or {}
    vars_list = None
    for candidate in (
        ((data.get("data") or {}).get("variables")),
        (data.get("variables")),
    ):
        if isinstance(candidate, list):
            vars_list = candidate
            break
    if vars_list is None:
        raise RuntimeError("Kunde inte hitta variables-lista i GraphQL-svaret")

    idx = {}
    vals = {}
    for i, v in enumerate(vars_list):
        ta = v.get("technicalAddress")
        if not ta:
            continue
        idx[ta] = i
        vals[ta] = v.get("value")
    return vals, idx

def write_by_ta(token, idx_map, ta, value):
    if ta not in idx_map:
        raise RuntimeError(f"TA saknas i idx_map: {ta}")
    key = f"{PVL_B64}:{idx_map[ta]}"
    gql(token, M_WRITE, {"v": [{"key": key, "value": str(value)}]})

def read_plan_array(vals, base):
    out = [0] * N
    missing = 0
    for i in range(N):
        ta = f"{base}({i})"
        if ta in vals:
            out[i] = to_int(vals.get(ta, 0))
        else:
            out[i] = 0
            missing += 1
    return out, missing

def handle_plan_readback(token, vals, idx_map, changed_ta, ack_ta, base, plan_type):
    changed = to_int(vals.get(changed_ta, 0))
    ack     = to_int(vals.get(ack_ta, 0))
    if changed == 1 and ack == 0:
        day_local = datetime.now(TZ).date()
        arr, missing = read_plan_array(vals, base)
        ones, ts = db_upsert_plan(plan_type, day_local, arr)
        log(f"✅ Readback {plan_type}: ones={ones} missing={missing} saved_utc={ts}")
        write_by_ta(token, idx_map, ack_ta, 1)
        log(f"✅ {plan_type}_ACK=1 skriven")

def handle_price_handshake(token, vals, idx_map):
    req = to_int(vals.get(TA_REQ, 0))
    ack = to_int(vals.get(TA_ACK, 0))
    day = to_int(vals.get(TA_DAY, 0))
    td_ready = to_int(vals.get(TA_TD_READY, 0))
    tm_ready = to_int(vals.get(TA_TM_READY, 0))

    if req == 1 and ack == 0:
        which = "today" if day == 0 else "tomorrow"

        if which == "tomorrow" and tm_ready == 1:
            log("✅ TM_READY=1 – skip push")
            return "ok"
        if which == "today" and td_ready == 1:
            log("✅ TD_READY=1 – skip push")
            return "ok"

        rows, day_local = fetch_prices(which)
        if which == "tomorrow" and len(rows) < 96:
            log(f"⚠️ Morgondagens priser saknas i DB ({len(rows)}/96) – väntar")
            return "wait_tomorrow"

        log(f"📤 Push {which}: {len(rows)} perioder")
        rank, ec, ex, slot_price = build_rank_and_masks(rows)
        today = date.today()
        oat_yday = daily_avg_oat(today - timedelta(days=1))
        oat_tmr  = daily_avg_oat(today + timedelta(days=1))
        push_to_arrigo(rank, ec, ex, day_local, oat_yday, oat_tmr, slot_price)

        write_by_ta(token, idx_map, TA_ACK, 1)
        log("✅ PI_PUSH_ACK=1 skriven")
        return "ok"

    return "idle"

def main():
    ensure_db_tables()
    token = arrigo_login()
    log("🔌 Orchestrator start (handshake + VV/HEAT readback)")

    sleep_ok = 10
    sleep_wait = 15   # snabbare retry när morgondagens priser saknas

    while True:
        try:
            vals, idx_map = read_vals_and_idx(token)

        except TransientAPIError as e:
            log(f"⚠️ Transient API (read): {e} – backoff 20s")
            time.sleep(20)
            continue

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                log("🔑 401 på read – relogin")
                token = arrigo_login()
                time.sleep(2)
                continue
            raise

        except Exception as e:
            log(f"❌ Read error: {e}")
            time.sleep(5)
            continue

        log(
            f"📡 REQ/ACK={to_int(vals.get(TA_REQ,0))}/{to_int(vals.get(TA_ACK,0))} "
            f"DAY={to_int(vals.get(TA_DAY,0))} TD/TM={to_int(vals.get(TA_TD_READY,0))}/{to_int(vals.get(TA_TM_READY,0))} | "
            f"VV(C/A)={to_int(vals.get(TA_VV_CHANGED,0))}/{to_int(vals.get(TA_VV_ACK,0))} "
            f"HEAT(C/A)={to_int(vals.get(TA_HEAT_CHANGED,0))}/{to_int(vals.get(TA_HEAT_ACK,0))}"
        )

        try:
            handle_plan_readback(token, vals, idx_map, TA_VV_CHANGED, TA_VV_ACK, BASE_VV, "VV_PLAN")
            handle_plan_readback(token, vals, idx_map, TA_HEAT_CHANGED, TA_HEAT_ACK, BASE_HEAT, "HEAT_PLAN")
            status = handle_price_handshake(token, vals, idx_map)

        except TransientAPIError as e:
            log(f"⚠️ Transient API (loop): {e} – backoff 20s")
            time.sleep(20)
            continue

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                log("🔑 401 under write/push – relogin")
                token = arrigo_login()
                time.sleep(2)
                continue
            raise

        except Exception as e:
            log(f"❌ Loop error: {e}")
            status = "ok"

        time.sleep(sleep_wait if status == "wait_tomorrow" else sleep_ok)

if __name__ == "__main__":
    main()
