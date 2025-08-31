#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Policy: Tider i databasen är UTC-naiva (DATETIME utan tz).
All dygnslogik görs i Europe/Stockholm.
In/ut:
  - API -> lokal SE (aware) -> UTC (aware) -> ta bort tz (naiv) -> DB
  - Läsning/visning -> UTC (naiv) -> gör aware (UTC) -> konvertera till SE
"""

import os, sys, json, logging, argparse, requests, pymysql
from datetime import datetime, date, time as dtime, timedelta
import pytz
import configparser
from typing import Tuple, List, Dict

# ======= KONFIG =======
LOG_INFO = os.getenv("SPOTPRIS_LOG_INFO", "/home/runerova/smartweb/spotpris_info.log")
LOG_ERR  = os.getenv("SPOTPRIS_LOG_ERR",  "/home/runerova/smartweb/spotpris_error.log")
PRICE_ZONE = os.getenv("PRICE_ZONE", "SE3")   # SE1..SE4
API_BASE = "https://www.elprisetjustnu.se/api/v1/prices"
# ======================

# ===== Logging =====
os.makedirs(os.path.dirname(LOG_INFO), exist_ok=True)
logging.basicConfig(
    filename=LOG_INFO,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
err_handler = logging.FileHandler(LOG_ERR)
err_handler.setLevel(logging.ERROR)
err_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.getLogger().addHandler(err_handler)
log = logging.getLogger("spotpris")

# ===== Tidszoner =====
STHLM = pytz.timezone("Europe/Stockholm")
UTC   = pytz.UTC

# ===== DB-config via ~/.my.cnf =====
def read_db_config() -> Dict:
    cfg = configparser.ConfigParser()
    cfg.read('/home/runerova/.my.cnf')
    return {
        'host': 'localhost',
        'user': cfg['client']['user'],
        'password': cfg['client']['password'],
        'database': 'smart_styrning',
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor,
        'autocommit': False,
    }

DB = read_db_config()

# ===== Hjälpfunktioner =====
def local_day_window_utc(local_day: date) -> Tuple[datetime, datetime]:
    """[lokal 00:00, 24:00) -> UTC-naiva gränser för DB-sökning."""
    start_local = STHLM.localize(datetime.combine(local_day, dtime(0,0)))
    end_local   = start_local + timedelta(days=1)
    return (start_local.astimezone(UTC).replace(tzinfo=None),
            end_local.astimezone(UTC).replace(tzinfo=None))

def is_dst(now_local: datetime) -> bool:
    """Sant om lokal aware-tid ligger i sommartid."""
    return bool(now_local.dst())

def choose_target_day(now_local: datetime) -> Tuple[date, str]:
    """
    Nord Pool / EPJN publicerar ~13 CET / ~14 CEST.
    Efter tröskeln siktar vi på imorgon.
    """
    today = now_local.date()
    threshold_hour = 14 if is_dst(now_local) else 13
    if now_local.hour >= threshold_hour:
        return today + timedelta(days=1), "tomorrow"
    return today, "today"

def count_rows_for_window(utc_start: datetime, utc_end: datetime) -> int:
    with pymysql.connect(**DB) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) AS n
            FROM electricity_prices
            WHERE datetime >= %s AND datetime < %s
        """, (utc_start, utc_end))
        return cur.fetchone()["n"]

def url_for(day_local: date) -> str:
    # https://www.elprisetjustnu.se/api/v1/prices/YYYY/MM-DD_SE3.json
    return f"{API_BASE}/{day_local:%Y}/{day_local:%m-%d}_{PRICE_ZONE}.json"

def fetch_prices(day_local: date) -> List[Dict]:
    url = url_for(day_local)
    log.info("🔎 Hämtar priser: %s", url)
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 404:
            log.info("❌ Inga priser publicerade för %s ännu (404).", day_local)
            return []
        r.raise_for_status()
        data = r.json()
        log.info("✅ Hämtat %d rader för %s (ex: %s ...)", len(data), day_local, json.dumps(data[:2], ensure_ascii=False))
        return data
    except Exception as e:
        log.error("Fel vid hämtning: %s", e)
        return []

def upsert_prices(data: List[Dict], target_day_local: date) -> Tuple[int,int,int]:
    """
    Upsert alla rader som tillhör target_day_local (tolkat i svensk tid).
    Returnerar (inserted, updated, skipped_for_other_day).
    """
    ins = upd = skip_other = 0
    if not data:
        return (0,0,0)

    with pymysql.connect(**DB) as conn, conn.cursor() as cur:
        # (Påverkar TIMESTAMP, inte DATETIME, men bra hygiene)
        cur.execute("SET time_zone = '+00:00'")
        for row in data:
            ts_str = row.get("time_start")
            if not ts_str:
                continue

            # Ex: '2025-08-30T00:00:00+02:00'
            ts = datetime.fromisoformat(ts_str)  # hanterar ±HH:MM
            ts_local = (STHLM.localize(ts) if ts.tzinfo is None else ts.astimezone(STHLM))

            # Filtrera på den lokala dagen
            if ts_local.date() != target_day_local:
                skip_other += 1
                continue

            price = float(row["SEK_per_kWh"])
            ts_utc_naive = ts_local.astimezone(UTC).replace(tzinfo=None)

            cur.execute("""
                INSERT INTO electricity_prices (datetime, price)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE
                    price = VALUES(price)
            """, (ts_utc_naive, price))

            # rowcount: 1 = insert, 2 = update (i denna upsert), 0 = unchanged
            if cur.rowcount == 1:
                ins += 1
                log.info("💾 Insert: %sZ => %.5f", ts_utc_naive, price)
            elif cur.rowcount == 2:
                upd += 1
                log.info("♻️ Update: %sZ => %.5f", ts_utc_naive, price)

        conn.commit()

    return (ins, upd, skip_other)

def verify_local_hour_coverage(local_day: date) -> List[int]:
    """
    Logga vilka lokala timmar (0..23) som finns i DB för local_day.
    Returnerar en lista med saknade timmar (kan vara tom).
    """
    utc_start, utc_end = local_day_window_utc(local_day)
    hours_present = set()
    rows = []

    with pymysql.connect(**DB) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT datetime, price
            FROM electricity_prices
            WHERE datetime >= %s AND datetime < %s
            ORDER BY datetime
        """, (utc_start, utc_end))
        rows = cur.fetchall()

    for r in rows:
        # DB har UTC-naiv -> gör aware i UTC och konvertera till SE
        dt_loc = UTC.localize(r["datetime"]).astimezone(STHLM)
        hours_present.add(dt_loc.hour)

    missing = [h for h in range(24) if h not in hours_present]
    if missing:
        log.warning("🧭 Lokala timmar saknas för %s: %s", local_day, missing)
    else:
        log.info("🧭 Alla 24 lokala timmar finns för %s.", local_day)
    return missing

# ===== Huvudflöde =====
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datum", help="YYYY-MM-DD (tvinga viss lokal dag; normalt behövs inte)")
    parser.add_argument("--zone",  default=PRICE_ZONE, help="Prisområde, t.ex. SE1..SE4 (default från env PRICE_ZONE)")
    args = parser.parse_args()

    # ev. överstyr prisområde från CLI
    global PRICE_ZONE
    PRICE_ZONE = args.zone

    now_local = datetime.now(STHLM)
    log.info("==> spotpris.py start (%s) | zone=%s", now_local.strftime("%Y-%m-%d %H:%M"), PRICE_ZONE)

    if args.datum:
        try:
            target_day_local = datetime.strptime(args.datum, "%Y-%m-%d").date()
            label = "forced"
        except ValueError:
            log.error("❌ Ogiltigt datumformat. Använd YYYY-MM-DD.")
            return 1
    else:
        target_day_local, label = choose_target_day(now_local)

    utc_start, utc_end = local_day_window_utc(target_day_local)
    have_before = count_rows_for_window(utc_start, utc_end)
    log.info("🎯 Mål-dag: %s (%s) | Rader i DB före: %d", target_day_local, label, have_before)

    data = fetch_prices(target_day_local)
    ins, upd, skip_other = upsert_prices(data, target_day_local)

    have_after = count_rows_for_window(utc_start, utc_end)
    log.info("📊 Resultat: inserted=%d, updated=%d, skip_other_day=%d | Rader i DB efter: %d",
             ins, upd, skip_other, have_after)

    # Verifiera lokala timmar (hjälper vid felsökning av 00–01)
    missing = verify_local_hour_coverage(target_day_local)

    # Komplett för dagen (23/24/25 beroende på DST) -> klart
    if have_after in (23, 24, 25) and not missing:
        log.info("✅ %s komplett (%d rader) och alla lokala timmar finns.", target_day_local, have_after)
        log.info("==> spotpris.py klar")
        return 0

    # Om vi siktade på imorgon och det saknas -> vänta till nästa körning (ingen fallback).
    if label == "tomorrow":
        log.warning("⏳ Imorgon ej komplett ännu (%d/24). Väntar till nästa körning.", have_after)
        log.info("==> spotpris.py klar")
        return 0

    # Om vi siktade på idag och det saknas mycket: gör ett extra försök (idempotent).
    if have_after < 23:
        log.warning("⚠️ Dagens data ofullständiga (%d/24). Försöker en gång till.", have_after)
        data2 = fetch_prices(now_local.date())
        ins2, upd2, skip2 = upsert_prices(data2, now_local.date())
        have_final = count_rows_for_window(*local_day_window_utc(now_local.date()))
        log.info("📈 Efter retry: inserted=%d, updated=%d | Rader i DB: %d", ins2, upd2, have_final)
        verify_local_hour_coverage(now_local.date())

    log.info("==> spotpris.py klar")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log.exception("Kritiskt fel: %s", e)
        sys.exit(1)
