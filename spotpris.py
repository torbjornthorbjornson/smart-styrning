#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, json, logging, argparse, requests, pymysql
from datetime import datetime, date, time as dtime, timedelta
import pytz
import configparser

# ===== Logging =====
LOG_INFO = "/home/runerova/smartweb/spotpris_info.log"
LOG_ERR  = "/home/runerova/smartweb/spotpris_error.log"
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

# ===== Zon / tid =====
STHLM = pytz.timezone("Europe/Stockholm")
UTC   = pytz.UTC
PRICE_ZONE = os.getenv("PRICE_ZONE", "SE3")  # SE1..SE4

# ===== DB-config via ~/.my.cnf =====
def read_db_config():
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

# ===== Hjälpare =====
def local_day_window_utc(local_day: date):
    """[lokal 00:00, 24:00) -> UTC-naivt intervall"""
    start_local = STHLM.localize(datetime.combine(local_day, dtime(0,0)))
    end_local   = start_local + timedelta(days=1)
    return (start_local.astimezone(UTC).replace(tzinfo=None),
            end_local.astimezone(UTC).replace(tzinfo=None))

def is_dst(now_local: datetime) -> bool:
    # True om vi är i sommartid
    return bool(STHLM.localize(now_local.replace(tzinfo=None)).dst())

def choose_target_day(now_local: datetime) -> tuple[date, str]:
    """Välj vilken dag vi ska fylla."""
    today = now_local.date()
    tomorrow = today + timedelta(days=1)
    # Nord Pool publicerar ~13 CET / 14 CEST
    threshold_hour = 14 if is_dst(now_local) else 13
    if now_local.hour >= threshold_hour:
        return tomorrow, "tomorrow"
    else:
        return today, "today"

def count_rows_for_window(utc_start, utc_end) -> int:
    with pymysql.connect(**DB) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) AS n
            FROM electricity_prices
            WHERE datetime >= %s AND datetime < %s
        """, (utc_start, utc_end))
        return cur.fetchone()["n"]

def url_for(day_local: date) -> str:
    # https://www.elprisetjustnu.se/api/v1/prices/YYYY/MM-DD_SE3.json
    return f"https://www.elprisetjustnu.se/api/v1/prices/{day_local:%Y}/{day_local:%m-%d}_{PRICE_ZONE}.json"

def fetch_prices(day_local: date):
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

def upsert_prices(data, target_day_local: date) -> tuple[int,int,int]:
    """
    Upsert (idempotent) alla rader som tillhör target_day_local i Stockholmstid.
    Returnerar (inserted, updated, skipped_for_other_day)
    """
    ins = upd = skip_other = 0
    if not data:
        return (0,0,0)

    with pymysql.connect(**DB) as conn, conn.cursor() as cur:
        for row in data:
            ts_str = row.get("time_start")
            if not ts_str:
                continue

            # Ex: '2025-08-30T00:00:00+02:00'
            ts_local = datetime.fromisoformat(ts_str)
            if ts_local.tzinfo is None:
                ts_local = STHLM.localize(ts_local)
            else:
                ts_local = ts_local.astimezone(STHLM)

            if ts_local.date() != target_day_local:
                # Filtrera bort rader som inte hör till mål-dagen (kan hända vid DST/gränsfall)
                skip_other += 1
                continue

            ts_utc_naive = ts_local.astimezone(UTC).replace(tzinfo=None)
            price = float(row["SEK_per_kWh"])

            cur.execute("""
                INSERT INTO electricity_prices (datetime, price)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE
                    price = VALUES(price)
            """, (ts_utc_naive, price))

            # MySQL/MariaDB: rowcount == 1 => insert, 2 => update
            if cur.rowcount == 1:
                ins += 1
                log.info("💾 Insert: %sZ => %.5f", ts_utc_naive, price)
            elif cur.rowcount == 2:
                upd += 1
                log.info("♻️ Update: %sZ => %.5f", ts_utc_naive, price)

        conn.commit()

    return (ins, upd, skip_other)

# ===== Huvudflöde =====
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datum", help="YYYY-MM-DD (tvinga viss lokal dag; normalt behövs inte)")
    args = parser.parse_args()

    now_local = datetime.now(STHLM)
    log.info("==> spotpris.py start (%s)", now_local.strftime("%Y-%m-%d %H:%M"))

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

    # ---- Beslutslogik: INGEN onödig fallback ----
    # Om vi redan har 24 (eller DST: 23/25) rader för mål-dagen: klart.
    if have_after in (24, 23, 25):
        log.info("✅ %s komplett (%d rader). Ingen fallback.", target_day_local, have_after)
        log.info("==> spotpris.py klar")
        return 0

    # Om det fortfarande saknas rader för mål-dagen:
    # - Om vi siktade på 'tomorrow' och det saknas -> det betyder troligen att NordPool ännu inte publicerat.
    #   Då väntar vi till nästa cron-run. Ingen fallback.
    if label == "tomorrow":
        log.warning("⏳ Imorgon ej komplett ännu (%d/24). Väntar till nästa körning, ingen fallback.", have_after)
        log.info("==> spotpris.py klar")
        return 0

    # - Om vi siktade på 'today' och vi saknar rader (kan vara nätfel) – prova hämta 'today' igen direkt (idempotent).
    if have_after < 23:
        log.warning("⚠️ Dagens data ofullständiga (%d/24). Försöker en gång till.", have_after)
        data2 = fetch_prices(now_local.date())
        ins2, upd2, skip2 = upsert_prices(data2, now_local.date())
        have_final = count_rows_for_window(*local_day_window_utc(now_local.date()))
        log.info("📈 Efter retry: inserted=%d, updated=%d | Rader i DB: %d", ins2, upd2, have_final)

    log.info("==> spotpris.py klar")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log.exception("Kritiskt fel: %s", e)
        sys.exit(1)
