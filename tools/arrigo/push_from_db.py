#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_from_db.py (allt i ett)
- Hämtar elpriser från DB (UTC) och bygger rank 0..23
- Räknar median, trösklar och maskar (extreme cheap/expensive)
- Loggar in mot Arrigo
- Läser PVL-variabellistan, bygger TA→index
- Skriver PRICE_RANK(h), PRICE_STAMP, EC/EX-maskar
- Skriver även OAT_mean_yday och OAT_mean_tomorrow
- Togglar PRICE_OK

Thresholds för maskar styrs via miljövariabler:
  ARRIGO_CHEAP_PCT   (default -0.30)  → t.ex. -0.30 betyder "cheap ≤ 70 % av median"
  ARRIGO_EXP_PCT     (default +0.50)  → t.ex. +0.50 betyder "exp ≥ 150 % av median"
"""

import os, re, base64
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pymysql, requests
from configparser import ConfigParser

TZ = ZoneInfo("Europe/Stockholm")
UTC = ZoneInfo("UTC")
LOG_PATH = "/home/runerova/smartweb/tools/arrigo/logs/arrigo_push.log"
PERIODS = 96  # HEAT kräver exakt 96 perioder

# ---- Hjälp ----
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

def getenv_any(names, required=False, default=None):
    for n in names:
        v = os.environ.get(n)
        if v: return v
    if required:
        raise KeyError(f"Saknar någon av: {', '.join(names)}")
    return default

def ensure_b64(s: str) -> str:
    s = s.strip()
    if re.fullmatch(r"[A-Za-z0-9+/=]+", s) and len(s) % 4 == 0:
        try:
            base64.b64decode(s)
            return s
        except Exception:
            pass
    return base64.b64encode(s.encode("utf-8")).decode("ascii")

def build_verify():
    if os.getenv("ARRIGO_INSECURE", "0") == "1": return False
    return os.getenv("REQUESTS_CA_BUNDLE") or True

def arrigo_login(login_url, user, password, verify):
    r = requests.post(login_url, json={"username": user, "password": password}, timeout=15, verify=verify)
    r.raise_for_status()
    tok = r.json().get("authToken")
    if not tok: raise SystemExit("Inget authToken i login-svar")
    return tok

def gql(url, token, query, variables):
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "variables": variables}, timeout=30,)
    r.raise_for_status()
    j = r.json()
    if "errors" in j:
        raise SystemExit("GraphQL-fel: " + str(j["errors"]))
    return j["data"]

# ---- Pris från DB ----
def fetch_prices(which: str):
    today_local = date.today()
    day_local = today_local + timedelta(days=1) if which=="tomorrow" else today_local
    start_local = datetime.combine(day_local, time(0,0), tzinfo=TZ)
    end_local   = start_local + timedelta(days=1)
    start_utc   = start_local.astimezone(UTC).replace(tzinfo=None)
    end_utc     = end_local.astimezone(UTC).replace(tzinfo=None)

    log(f"📅 Hämtar priser för {which} ({day_local}) → UTC[{start_utc}→{end_utc}]")

    conn = pymysql.connect(**read_db_config())
    with conn, conn.cursor() as cur:
        cur.execute("SELECT datetime, price FROM electricity_prices WHERE datetime >= %s AND datetime < %s ORDER BY datetime", (start_utc, end_utc))
        rows = cur.fetchall()
    return rows, day_local

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

# ---- OAT ----
def daily_avg_oat(day_local: date):
    start_local = datetime.combine(day_local,time(0,0),tzinfo=TZ)
    end_local   = start_local+timedelta(days=1)
    start_utc   = start_local.astimezone(UTC).replace(tzinfo=None)
    end_utc     = end_local.astimezone(UTC).replace(tzinfo=None)
    conn = pymysql.connect(**read_db_config())
    with conn, conn.cursor() as cur:
        cur.execute("SELECT AVG(temperature) AS avgtemp FROM weather WHERE timestamp >= %s AND timestamp < %s",(start_utc,end_utc))
        row=cur.fetchone()
    return round(float(row["avgtemp"]),1) if row and row["avgtemp"] else None

# ---- Push ----
def push_to_arrigo(gql, token, pvl_b64, rank, masks, day_local, oat_yday, oat_tmr):

    
    data = gql(
    "query($path:String!){ data(path:$path){ variables{ technicalAddress } } }",
    {"path": pvl_b64},
)

    vars_list = (data.get("data") or {}).get("variables") or []

    idx_rank, idx_stamp = {}, None
    idx_price_ok=None
    idx_oat_yday=idx_oat_tmr=None
    idx_masks={}

    for i,v in enumerate(vars_list):
        ta=(v.get("technicalAddress") or "").strip()
        m=re.search(r"\.PRICE_RANK\((\d+)\)$",ta)
        if m: idx_rank[int(m.group(1))]=i; continue
        if ta.endswith(".PRICE_OK"): idx_price_ok=i; continue
        if ta.endswith(".PRICE_STAMP"): idx_stamp=i; continue
        if ta.endswith(".OAT_mean_yday"): idx_oat_yday=i; continue
        if ta.endswith(".OAT_mean_tomorrow"): idx_oat_tmr=i; continue
        if ta.endswith(".EC_MASK_L"): idx_masks["EC_MASK_L"]=i; continue
        if ta.endswith(".EC_MASK_H"): idx_masks["EC_MASK_H"]=i; continue
        if ta.endswith(".EX_MASK_L"): idx_masks["EX_MASK_L"]=i; continue
        if ta.endswith(".EX_MASK_H"): idx_masks["EX_MASK_H"]=i; continue

    if idx_price_ok is not None:
        gql(
            "mutation($v:[VariableKeyValue!]!){writeData(variables:$v)}",
            {"v":[{"key":f"{pvl_b64}:{idx_price_ok}","value":"0"}]}
  )

        log("🔒 PRICE_OK=0")

    writes=[]
    for h in range(24):
        if h in idx_rank:
            writes.append({"key":f"{pvl_b64}:{idx_rank[h]}","value":str(rank[h])})
    if idx_stamp is not None:
        writes.append({"key":f"{pvl_b64}:{idx_stamp}","value":day_local.strftime("%Y%m%d")})
    if idx_oat_yday is not None and oat_yday is not None:
        writes.append({"key":f"{pvl_b64}:{idx_oat_yday}","value":str(oat_yday)})
    if idx_oat_tmr is not None and oat_tmr is not None:
        writes.append({"key":f"{pvl_b64}:{idx_oat_tmr}","value":str(oat_tmr)})
    for k,v in masks.items():
        if k in idx_masks:
            writes.append({"key":f"{pvl_b64}:{idx_masks[k]}","value":str(v)})
    log(f"🧩 Masks: {masks}")

    gql(
        "mutation($v:[VariableKeyValue!]!){writeData(variables:$v)}",
        {"v":writes}
   )

    log(f"✅ Skrev {len(writes)} variabler")

    if idx_price_ok is not None:
        gql(
        "mutation($v:[VariableKeyValue!]!){writeData(variables:$v)}",
        {"v":[{"key":f"{pvl_b64}:{idx_price_ok}","value":"1"}]}
        )

        log("🔓 PRICE_OK=1")



# OBS: denna modul körs inte fristående längre
# push_to_arrigo() anropas av orchestrator
