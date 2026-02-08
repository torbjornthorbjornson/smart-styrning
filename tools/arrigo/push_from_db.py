#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_from_db.py  (WORKER / LIBRARY)

ANSVAR:
- Läser elpriser från MariaDB (UTC)
- Normaliserar till 96 perioder
- Bygger rankning och EC/EX-masker
- Pushar data till Arrigo VIA BEFINTLIG TOKEN

VIKTIGT:
- Loggar ALDRIG in mot Arrigo
- Äger ALDRIG token
- Körs ENDAST via orchestrator
"""

import re
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pymysql
from configparser import ConfigParser

# =========================
# TID
# =========================
TZ  = ZoneInfo("Europe/Stockholm")
UTC = ZoneInfo("UTC")

PERIODS = 96  # HEAT kräver exakt 96 perioder

# =========================
# DB
# =========================
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

# =========================
# PRISER FRÅN DB
# =========================
def fetch_prices_for_local_day(day_local: date):
    """
    Hämtar exakt ett lokalt svenskt dygn (00–24)
    trots att DB lagrar UTC över kalenderdygn.
    """
    start_local = datetime.combine(day_local, time(0, 0), tzinfo=TZ)
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
# PERIOD-NORMALISERING
# =========================
def normalize_periods(rows):
    per_slot = {i: [] for i in range(PERIODS)}

    for r in rows:
        dt = r["datetime"].replace(tzinfo=UTC).astimezone(TZ)
        idx = dt.hour * 4 + (dt.minute // 15)
        if 0 <= idx < PERIODS:
            per_slot[idx].append(float(r["price"]))

    out = []
    for i in range(PERIODS):
        price = sum(per_slot[i]) / len(per_slot[i]) if per_slot[i] else 0.0
        out.append((i, price))

    return out

# =========================
# MASKER & RANK
# =========================
def pack_masks(slots):
    nwords = (PERIODS + 31) // 32
    words = [0] * nwords
    for s in slots:
        words[s // 32] |= (1 << (s % 32))
    return words

def build_rank_and_masks(rows):
    slot_price = normalize_periods(rows)
    prices = [p for _, p in slot_price]

    sorted_prices = sorted(prices)
    mid = PERIODS // 2
    median = (sorted_prices[mid - 1] + sorted_prices[mid]) / 2.0

    cheap_thr = median * 0.5
    exp_thr   = median * 1.5

    cheap_slots = [i for i, p in slot_price if p <= cheap_thr]
    exp_slots   = [i for i, p in slot_price if p >= exp_thr]

    ec_masks = pack_masks(cheap_slots)
    ex_masks = pack_masks(exp_slots)

    sorted_idx = sorted(range(PERIODS), key=lambda i: slot_price[i][1])
    idx_to_rank = {i: r for r, i in enumerate(sorted_idx)}
    rank = [idx_to_rank[i] for i, _ in slot_price]

    return rank, ec_masks, ex_masks, slot_price

# =========================
# OAT
# =========================
def daily_avg_oat(day_local: date):
    start_local = datetime.combine(day_local, time(0, 0), tzinfo=TZ)
    end_local   = start_local + timedelta(days=1)

    start_utc = start_local.astimezone(UTC).replace(tzinfo=None)
    end_utc   = end_local.astimezone(UTC).replace(tzinfo=None)

    conn = pymysql.connect(**read_db_config())
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT AVG(temperature) AS avgtemp FROM weather WHERE timestamp >= %s AND timestamp < %s",
            (start_utc, end_utc)
        )
        row = cur.fetchone()

    return round(float(row["avgtemp"]), 1) if row and row["avgtemp"] is not None else None

# =========================
# PUSH (ANVÄNDER ORCHESTRATORNS TOKEN)
# =========================
def push_to_arrigo(
    gql_fn,
    token,
    pvl_b64,
    rank,
    ec_masks,
    ex_masks,
    day_local,
    oat_yday,
    oat_tmr,
    slot_price,
):
    """
    Pushar data till Arrigo.
    Förutsätter giltig token från orchestrator.
    """

    data = gql_fn(
        token,
        'query($p:String!){ data(path:$p){ variables{ technicalAddress } } }',
        {"p": pvl_b64},
    )

    vars_list = (data.get("data") or {}).get("variables") or []
        
    print("=== VARS_LIST (first 30) ===")
    for i, v in enumerate(vars_list[:30]):
        print(f"{i:02d}  {v.get('technicalAddress')}")
    print("=== END VARS_LIST ===")

    idx = {}
    for i, v in enumerate(vars_list):
        ta = (v.get("technicalAddress") or "").strip()
        idx[ta] = i

    writes = []

    for i in range(PERIODS):
        ta = f"PRICE_RANK({i})"
        if ta in idx:
            writes.append({"key": f"{pvl_b64}:{idx[ta]}", "value": str(rank[i])})

    for i, price in slot_price:
        ta = f"PRICE_VAL({i})"
        if ta in idx:
            writes.append({"key": f"{pvl_b64}:{idx[ta]}", "value": f"{price:.2f}"})

    if "PRICE_STAMP" in idx:
        writes.append({"key": f"{pvl_b64}:{idx['PRICE_STAMP']}", "value": day_local.strftime("%Y%m%d")})

    if oat_yday is not None and "OAT_mean_yday" in idx:
        writes.append({"key": f"{pvl_b64}:{idx['OAT_mean_yday']}", "value": str(oat_yday)})

    if oat_tmr is not None and "OAT_mean_tomorrow" in idx:
        writes.append({"key": f"{pvl_b64}:{idx['OAT_mean_tomorrow']}", "value": str(oat_tmr)})

    for i, val in enumerate(ec_masks, start=1):
        ta = f"EC_MASK32_{i}"
        if ta in idx:
            writes.append({"key": f"{pvl_b64}:{idx[ta]}", "value": str(val)})

    for i, val in enumerate(ex_masks, start=1):
        ta = f"EX_MASK32_{i}"
        if ta in idx:
            writes.append({"key": f"{pvl_b64}:{idx[ta]}", "value": str(val)})

    gql_fn(
        token,
        "mutation($v:[VariableKeyValue!]!){ writeData(variables:$v) }",
        {"v": writes},
    )
