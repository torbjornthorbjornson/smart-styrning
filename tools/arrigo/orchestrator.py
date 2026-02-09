#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime, date, timedelta, time as dtime
import pytz
import pymysql
import requests
import base64
from configparser import ConfigParser

from push_from_db import (
    build_rank_and_masks,
    daily_avg_oat,
    push_to_arrigo,
)


# ==================================================
# TIDSZONER – FACIT
# ==================================================
# MariaDB lagrar electricity_prices.datetime som UTC (naiv DATETIME).
# spotpris.py skriver UTC som kan spänna över två kalenderdygn.
#
# Orchestratorn definierar ett LOKALT svenskt dygn (Europe/Stockholm)
# och översätter detta till ett UTC-fönster vid DB-frågor.
#
# Detta är ENDA platsen där lokal ↔ UTC-konvertering sker.
# Se: TODO/016_TIME_CONTRACT/README.md

UTC   = pytz.UTC
STHLM = pytz.timezone("Europe/Stockholm")


def _avg_price_per_local_hour(rows):
    """Returnerar dict {0..23: avg_price} baserat på DB-rader (UTC-naiv datetime)."""
    sums = {}
    counts = {}
    for r in rows or []:
        try:
            dt_utc = r["datetime"].replace(tzinfo=UTC)
            dt_local = dt_utc.astimezone(STHLM)
            hour = int(dt_local.hour)
            price = float(r["price"])
        except Exception:
            continue
        sums[hour] = sums.get(hour, 0.0) + price
        counts[hour] = counts.get(hour, 0) + 1
    return {h: (sums[h] / counts[h]) for h in sums if counts.get(h)}


def _build_hourly_rank(rows):
    """Bygger rank[0..23] där 0=billigast timme, 23=dyrast."""
    hour_avg = _avg_price_per_local_hour(rows)
    if len(hour_avg) < 20:
        return None

    hours = list(range(24))
    # Om någon timme saknas: avbryt hellre än att skriva skräp.
    if any(h not in hour_avg for h in hours):
        return None

    sorted_hours = sorted(hours, key=lambda h: (hour_avg[h], h))
    rank_by_hour = {h: i for i, h in enumerate(sorted_hours)}
    return [rank_by_hour[h] for h in hours]


def _words32_to_masks_64(ec_words, ex_words):
    """Konverterar 32-bitarsord (list) till Arrigo-masker L/H (2x64-bit).

    För 96 perioder fås normalt 3 ord. Vi packar ord[0..1] till L och ord[2] till H.
    """

    def pack_2x64(words):
        words = list(words or [])
        # säkerställ minst 3 ord
        while len(words) < 3:
            words.append(0)
        lo64 = int(words[0]) | (int(words[1]) << 32)
        hi64 = int(words[2])
        return lo64, hi64

    ec_l, ec_h = pack_2x64(ec_words)
    ex_l, ex_h = pack_2x64(ex_words)
    return {
        "EC_MASK_L": ec_l,
        "EC_MASK_H": ec_h,
        "EX_MASK_L": ex_l,
        "EX_MASK_H": ex_h,
    }


def today_local_date() -> date:
    """Returnerar dagens datum i svensk lokal tid."""
    return datetime.now(UTC).astimezone(STHLM).date()


def local_day_to_utc_window(local_date: date):
    """Bygger UTC-fönster för ett helt svenskt lokalt dygn."""
    local_midnight = STHLM.localize(datetime.combine(local_date, dtime(0, 0)))
    utc_start = local_midnight.astimezone(UTC).replace(tzinfo=None)
    utc_end   = (local_midnight + timedelta(days=1)).astimezone(UTC).replace(tzinfo=None)
    return utc_start, utc_end


# ==================================================
# ARRIGO / EXOL – KONFIG
# ==================================================
LOGIN_URL   = os.getenv("ARRIGO_LOGIN_URL")
GRAPHQL_URL = os.getenv("ARRIGO_GRAPHQL_URL")
USER        = os.getenv("ARRIGO_USER") or os.getenv("ARRIGO_USERNAME")
PASS        = os.getenv("ARRIGO_PASS") or os.getenv("ARRIGO_PASSWORD")

PVL_RAW = os.getenv("ARRIGO_PVL_B64") or os.getenv("ARRIGO_PVL_PATH")
if not PVL_RAW:
    raise SystemExit("Saknar ARRIGO_PVL_B64 / ARRIGO_PVL_PATH")

# säkerställ base64 (Arrigo kräver detta)
try:
    base64.b64decode(PVL_RAW)
    PVL_B64 = PVL_RAW
except Exception:
    PVL_B64 = base64.b64encode(PVL_RAW.encode("utf-8")).decode("ascii")



TA_REQ = "Huvudcentral_C1.PI_PUSH_REQ"
TA_ACK = "Huvudcentral_C1.PI_PUSH_ACK"
TA_DAY = "Huvudcentral_C1.PI_PUSH_DAY"

Q_READ  = "query($p:String!){ data(path:$p){ variables{ technicalAddress value } } }"
M_WRITE = "mutation($v:[VariableKeyValue!]!){ writeData(variables:$v) }"


# ==================================================
# DB / INFRA
# ==================================================
DB_NAME   = "smart_styrning"
MYCNF     = "/home/runerova/.my.cnf"
SLEEP_SEC = 4


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def to_int(x, default=0):
    if isinstance(x, bool):
        return 1 if x else 0
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
    )


# ==================================================
# ARRIGO API – HJÄLPARE
# ==================================================
def arrigo_login():
    r = requests.post(
        LOGIN_URL,
        json={"username": USER, "password": PASS},
        timeout=20,
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


def write_ack(token, idx, value):
    key = f"{PVL_B64}:{idx[TA_ACK]}"
    gql(token, M_WRITE, {"v": [{"key": key, "value": str(value)}]})


# ==================================================
# DB → PRISER
# ==================================================
def db_fetch_prices_for_day(day_local: date):
    utc_start, utc_end = local_day_to_utc_window(day_local)

    conn = pymysql.connect(**read_db_config())
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT datetime, price
            FROM electricity_prices
            WHERE datetime >= %s AND datetime < %s
            ORDER BY datetime
            """,
            (utc_start, utc_end),
        )
        return cur.fetchall()


# ==================================================
# MAIN – ORCHESTRATOR
# ==================================================
def main():
    token = arrigo_login()
    log("🔌 Orchestrator startad")
    log("🚨 ORCHESTRATOR VERSION 2026-02-08 20:45 🚨")

    def gql_wrapper(query, variables):
        # token kommer från omgivande scope
        return gql(token, query, variables)

    while True:
        try:
            vals, idx = read_vals_and_idx(token)
            log(f"RAW PI_PUSH_REQ = {vals.get(TA_REQ)}")
            if TA_REQ not in vals:
                 log(f"❌ TA_REQ saknas! keys={list(vals.keys())[:10]} ...")
            else:
                 log(f"✅ TA_REQ hittad, raw={vals[TA_REQ]!r}, type={type(vals[TA_REQ])}")

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

        log(f"REQ={req} ACK={ack} DAY={day}")

        # ==================================================
        # BESLUT: SKA NYA PRISER PUSHAS TILL ARRIGO?
        # ==================================================
        if req == 1 and ack == 0:

            target_day = today_local_date() + timedelta(days=day)
            log(f"📥 EXOL begär priser för lokalt dygn: {target_day}")

            rows = db_fetch_prices_for_day(target_day)
            log(f"📊 DB-perioder: {len(rows)}")

            # Om DB saknar data (vanligt för "imorgon" tidigt), vänta utan att ACK:a.
            # För 96 perioder vill vi i praktiken ha nära full dygnstäckning.
            if not rows or len(rows) < 90:
                log("⚠️ För få prisrader i DB för 96 perioder – väntar med push (ACK lämnas 0).")
                time.sleep(SLEEP_SEC)
                continue

            # Primärt: 96-perioders rank + masker från push_from_db.
            brm = build_rank_and_masks(rows)
            rank = None
            masks = None

            if isinstance(brm, tuple) and len(brm) >= 4:
                rank, ec_words, ex_words, _slot_price = brm[:4]
                masks = _words32_to_masks_64(ec_words, ex_words)
            elif isinstance(brm, tuple) and len(brm) == 2:
                rank, masks = brm
            else:
                log(f"⚠️ Oväntat returformat från build_rank_and_masks: {type(brm)}")
                time.sleep(SLEEP_SEC)
                continue

            if not isinstance(rank, (list, tuple)) or len(rank) < 24:
                log(f"⚠️ Oväntad rank: type={type(rank)} len={getattr(rank, '__len__', lambda: 'n/a')()}")
                time.sleep(SLEEP_SEC)
                continue

            # Fallback om vi av någon anledning får 24-timmarsrank.
            if len(rank) != 96:
                log(f"ℹ️ Rank-längd={len(rank)} (förväntat 96). Kör bakåtkompatibelt.")

            if not isinstance(masks, dict):
                log(f"⚠️ Oväntat mask-format ({type(masks)}) – väntar med push.")
                time.sleep(SLEEP_SEC)
                continue

            oat_yday = daily_avg_oat(target_day - timedelta(days=1))
            oat_tmr  = daily_avg_oat(target_day + timedelta(days=1))

            log("📤 Pushar till Arrigo")
            push_to_arrigo(
            gql_wrapper,  # wrapper med bundet token
            token,
            PVL_B64,
            rank,
            masks,
            target_day,
            oat_yday,
            oat_tmr,
        )




            write_ack(token, idx, 1)
            log("✅ PI_PUSH_ACK satt")

        time.sleep(SLEEP_SEC)


# ==================================================
# ENTRYPOINT
# ==================================================
if __name__ == "__main__":
    main()
