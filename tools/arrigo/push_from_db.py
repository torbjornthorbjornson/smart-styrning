#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_from_db.py
- Hämtar elpriser från DB (UTC) och bygger rank 0..23
- Räknar median, trösklar och maskar (extreme cheap/expensive)
- Loggar in mot Arrigo
- Läser PVL-variabellistan, bygger TA→index
- Skriver PRICE_RANK(h), PRICE_STAMP, EC/EX-maskar
- Skriver även OAT_mean_yday och OAT_mean_tomorrow
- Nytt: Skriver Price_Val(0..23) = faktiska timpriser
- Togglar PRICE_OK
"""

import os, re, base64
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pymysql, requests
from configparser import ConfigParser

TZ = ZoneInfo("Europe/Stockholm")
UTC = ZoneInfo("UTC")
LOG_PATH = "/home/runerova/smartweb/tools/arrigo/logs/arrigo_push.log"

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

def gql(url, token, query, variables, verify):
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "variables": variables}, timeout=30, verify=verify)
    r.raise_for_status()
    j = r.json()
    if "errors" in j:
        raise SystemExit("GraphQL-fel: " + str(j["errors"]))
    return j["data"]

# ---- Pris från DB ----
def fetch_prices(which: str):
    # Bygg svensk kalenderdag
    today_local = datetime.now(UTC).astimezone(TZ).date()
    day_local = today_local + timedelta(days=1) if which=="tomorrow" else today_local
    start_local = datetime.combine(day_local, time(0,0), tzinfo=TZ)
    end_local   = start_local + timedelta(days=1)
    start_utc   = start_local.astimezone(UTC).replace(tzinfo=None)
    end_utc     = end_local.astimezone(UTC).replace(tzinfo=None)

    log(f"📅 Hämtar priser för {which} ({day_local}) → UTC[{start_utc}→{end_utc}]")

    conn = pymysql.connect(**read_db_config())
    with conn, conn.cursor() as cur:
        cur.execute("""
            SELECT datetime, price FROM electricity_prices
            WHERE datetime >= %s AND datetime < %s
            ORDER BY datetime
        """, (start_utc, end_utc))
        rows = cur.fetchall()

    if len(rows) != 24:
        log(f"⚠️ Antal timmar i DB: {len(rows)} (förväntat 24)")
    return rows, day_local

def normalize_to_24(rows):
    """Bygg timmap utifrån svensk tid (UTC → Europe/Stockholm)."""
    per_hour = {h: [] for h in range(24)}
    for r in rows:
        h = r["datetime"].replace(tzinfo=UTC).astimezone(TZ).hour
        per_hour[h].append(float(r["price"]))
    out = []
    for h in range(24):
        if per_hour[h]:
            price = sum(per_hour[h])/len(per_hour[h])
        else:
            price = 0.0  # markera saknad timme
        out.append((h, price))
    return out

def build_rank_and_masks(rows):
    hour_price = normalize_to_24(rows)
    sorted_prices = sorted([p for _,p in hour_price])
    median = (sorted_prices[11] + sorted_prices[12])/2.0

    cheap_pct = float(getenv_any(["ARRIGO_CHEAP_PCT"], default="-0.50"))
    exp_pct   = float(getenv_any(["ARRIGO_EXP_PCT"],   default="+1.50"))
    cheap_thr = median * (1.0 + cheap_pct)
    exp_thr   = median * (1.0 + exp_pct)

    cheap_hours = [h for h,p in hour_price if p <= cheap_thr]
    exp_hours   = [h for h,p in hour_price if p >= exp_thr]

    def pack_mask(hours):
        bits=0
        for h in hours:
            bits |= (1<<h)
        return bits & 0xFFFF, (bits>>16)&0xFFFF

    ecL, ecH = pack_mask(cheap_hours)
    exL, exH = pack_mask(exp_hours)

    sorted_hours = sorted(range(24), key=lambda h: hour_price[h][1])
    hour_to_rank = {h:i for i,h in enumerate(sorted_hours)}
    rank = [hour_to_rank[h] for h,_ in hour_price]

    log(f"📊 Median={median:.3f}, cheap_thr={cheap_thr:.3f}, exp_thr={exp_thr:.3f}")
    return rank, {"EC_MASK_L":ecL,"EC_MASK_H":ecH,"EX_MASK_L":exL,"EX_MASK_H":exH}, hour_price

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
def push_to_arrigo(rank, masks, day_local, oat_yday, oat_tmr, hour_price):
    login_url   = getenv_any(["ARRIGO_LOGIN_URL"], True)
    graphql_url = getenv_any(["ARRIGO_GRAPHQL_URL"], True)
    user        = getenv_any(["ARRIGO_USER","ARRIGO_USERNAME"], True)
    password    = getenv_any(["ARRIGO_PASS","ARRIGO_PASSWORD"], True)
    pvl_raw     = getenv_any(["ARRIGO_PVL_B64","ARRIGO_PVL_PATH"], True)
    pvl_b64     = ensure_b64(pvl_raw)
    verify      = build_verify()

    token = arrigo_login(login_url,user,password,verify)
    data = gql(graphql_url,token,'query($path:String!){ data(path:$path){ variables{ technicalAddress } } }',{"path":pvl_b64},verify)
    vars_list = (data.get("data") or {}).get("variables") or []

    idx_rank, idx_stamp = {}, None
    idx_price_ok=None
    idx_oat_yday=idx_oat_tmr=None
    idx_masks={}
    idx_vals={}

    for i,v in enumerate(vars_list):
        ta=(v.get("technicalAddress") or "").strip()
        m_rank=re.search(r"\.price_rank(?:_|\()(\d+)\)?$", ta, re.IGNORECASE)
        if m_rank: idx_rank[int(m_rank.group(1))]=i; continue
        m_val=re.search(r"\.price_val(?:_|\()(\d+)\)?$", ta, re.IGNORECASE)
        if m_val: idx_vals[int(m_val.group(1))]=i; continue
        if ta.endswith(".PRICE_OK"): idx_price_ok=i; continue
        if ta.endswith(".PRICE_STAMP"): idx_stamp=i; continue
        if ta.endswith(".OAT_mean_yday"): idx_oat_yday=i; continue
        if ta.endswith(".OAT_mean_tomorrow"): idx_oat_tmr=i; continue
        if ta.endswith(".EC_MASK_L"): idx_masks["EC_MASK_L"]=i; continue
        if ta.endswith(".EC_MASK_H"): idx_masks["EC_MASK_H"]=i; continue
        if ta.endswith(".EX_MASK_L"): idx_masks["EX_MASK_L"]=i; continue
        if ta.endswith(".EX_MASK_H"): idx_masks["EX_MASK_H"]=i; continue

    log(f"🧭 PRICE_RANK map: {sorted(idx_rank.items())}")
    log(f"🧭 Price_Val  map: {sorted(idx_vals.items())}")

    if idx_price_ok is not None:
        gql(graphql_url,token,"mutation($v:[VariableKeyValue!]!){writeData(variables:$v)}",{"v":[{"key":f"{pvl_b64}:{idx_price_ok}","value":"0"}]},verify)
        log("🔒 PRICE_OK=0")

    writes=[]
    for h in range(24):
        if h in idx_rank:
            writes.append({"key":f"{pvl_b64}:{idx_rank[h]}","value":str(rank[h])})
    for h,price in hour_price:
        if h in idx_vals:
            writes.append({"key":f"{pvl_b64}:{idx_vals[h]}","value":f"{price:.2f}"})
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

    gql(graphql_url,token,"mutation($v:[VariableKeyValue!]!){writeData(variables:$v)}",{"v":writes},verify)
    log(f"✅ Skrev {len(writes)} variabler")

    if idx_price_ok is not None:
        gql(graphql_url,token,"mutation($v:[VariableKeyValue!]!){writeData(variables:$v)}",{"v":[{"key":f"{pvl_b64}:{idx_price_ok}","value":"1"}]},verify)
        log("🔓 PRICE_OK=1")

# ---- Main ----
def main():
    which=os.getenv("RANK_WHEN","today")
    rows,day_local=fetch_prices(which)
    rank,masks,hour_price=build_rank_and_masks(rows)
    today=date.today()
    oat_yday=daily_avg_oat(today-timedelta(days=1))
    oat_tmr =daily_avg_oat(today+timedelta(days=1))
    push_to_arrigo(rank,masks,day_local,oat_yday,oat_tmr,hour_price)

if __name__=="__main__":
    try: main()
    except Exception as e:
        log(f"💥 Fel: {e}"); raise
