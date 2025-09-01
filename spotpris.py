#!/usr/bin/env python3
import requests
import pymysql
import logging
import argparse
from datetime import datetime, timedelta, time
import pytz
import configparser

# === Logging ===
logging.basicConfig(
    filename='/home/runerova/smartweb/spotpris_info.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
error_handler = logging.FileHandler('/home/runerova/smartweb/spotpris_error.log')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logging.getLogger().addHandler(error_handler)

# === Läs från ~/.my.cnf ===
def read_db_config():
    config = configparser.ConfigParser()
    config.read('/home/runerova/.my.cnf')
    return {
        'host': 'localhost',
        'user': config['client']['user'],
        'password': config['client']['password'],
        'database': 'smart_styrning',
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor,
    }

DB_CONFIG = read_db_config()
STHLM = pytz.timezone("Europe/Stockholm")
UTC = pytz.UTC

def fetch_prices(date_obj):
    area = "SE3"
    date_str = date_obj.strftime("%Y/%m-%d")
    url = f"https://www.elprisetjustnu.se/api/v1/prices/{date_str}_{area}.json"
    logging.info(f"Försöker hämta priser från: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        logging.info(f"Dagens priser hämtade framgångsrikt: {data[:2]} ...")
        return data
    except Exception as e:
        logging.warning(f"Inga elpriser tillgängliga eller fel uppstod: {e}")
        return []

def parse_and_save(data, target_date_local):
    """Spara priser i UTC-naiv tid. Validera att posten hör till target_date_local i Stockholmstid."""
    if not data:
        return 0
    saved = 0
    conn = pymysql.connect(**DB_CONFIG)
    with conn:
        with conn.cursor() as cursor:
            for row in data:
                ts_str = row.get("time_start")
                if not ts_str:
                    continue
                ts_parsed = datetime.fromisoformat(ts_str)  # ofta med +02:00
                if ts_parsed.tzinfo is None:
                    ts_local = STHLM.localize(ts_parsed)
                else:
                    ts_local = ts_parsed.astimezone(STHLM)

                # Spara bara rader som tillhör rätt DYGN i Stockholmstid
                if ts_local.date() != target_date_local.date():
                    logging.info(f"⏩ Skippad: fel datum ({ts_local.date()} != {target_date_local.date()})")
                    continue

                # Konvertera till UTC-naiv innan INSERT (MariaDB DATETIME saknar tz)
                ts_utc_naive = ts_local.astimezone(UTC).replace(tzinfo=None)

                price = row.get("SEK_per_kWh")
                if price is None:
                    continue

                try:
                    cursor.execute(
                        "INSERT INTO electricity_prices (datetime, price) VALUES (%s, %s)",
                        (ts_utc_naive, price)
                    )
                    logging.info(f"💾 Sparat: {ts_utc_naive}Z => {price} kr/kWh")
                    saved += 1
                except pymysql.err.IntegrityError:
                    logging.info(f"⏩ Skippad (fanns redan): {ts_utc_naive}Z")
        conn.commit()

    # Informationslogg vid 23/25 timmar (DST)
    day_start_local = STHLM.localize(datetime.combine(target_date_local.date(), time(0,0)))
    if saved in (23, 25):
        if day_start_local.dst():
            logging.info("☀️ Sommartid: 23 timmar är normalt den här dagen.")
        else:
            logging.info("❄️ Vintertid: 25 timmar är normalt den här dagen.")
    return saved

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datum", help="Datum i formatet ÅÅÅÅ-MM-DD")
    args = parser.parse_args()

    logging.info("==> spotpris.py startade")
    date_str = args.datum or datetime.now().strftime("%Y-%m-%d")
    try:
        target_date_local = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        logging.error("❌ Ogiltigt datumformat. Använd ÅÅÅÅ-MM-DD.")
        return

    data = fetch_prices(target_date_local)
    saved = parse_and_save(data, target_date_local)

    if saved == 0:
        fallback_date = target_date_local - timedelta(days=1)
        logging.warning(f"🔁 Försöker med gårdagens data istället: {fallback_date.date()}")
        data = fetch_prices(fallback_date)
        saved = parse_and_save(data, fallback_date)

    logging.info(f"✅ {saved} priser sparade.")
    logging.info("==> spotpris.py klar")

if __name__ == "__main__":
    main()
