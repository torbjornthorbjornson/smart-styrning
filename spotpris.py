
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
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
error_handler.setFormatter(formatter)
logging.getLogger().addHandler(error_handler)

# === Läs DB‑uppgifter från ~/.my.cnf ===
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
STH = pytz.timezone("Europe/Stockholm")

def fetch_prices(date_obj):
    area = "SE3"
    date_str = date_obj.strftime("%Y/%m-%d")
    url = f"https://www.elprisetjustnu.se/api/v1/prices/{date_str}_{area}.json"
    logging.info(f"Försöker hämta priser från: {url}")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        logging.info(f"Dagens priser hämtade framgångsrikt: {data[:2]} ...")
        return data
    except Exception as e:
        logging.warning(f"Inga elpriser tillgängliga eller fel uppstod: {e}")
        return []

def parse_and_save(data, target_date_local):
    """Spara alltid i DB som UTC (naiv DATETIME). Filtrera så att vi bara sparar rader
       som tillhör det *lokala* dygnet target_date_local (Europe/Stockholm)."""
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

                # API ger lokal tid med offset, t.ex. 2025-08-28T00:00:00+02:00
                ts_local = datetime.fromisoformat(ts_str)  # offset-aware
                # Filtrera: endast timmar som tillhör det valda lokala dygnet
                if ts_local.astimezone(STH).date() != target_date_local.date():
                    logging.info(f"⏩ Skippad: fel datum ({ts_local.date()} != {target_date_local.date()})")
                    continue

                price = row.get("SEK_per_kWh")
                if price is None:
                    continue

                # Konvertera till UTC och ta bort tzinfo (MySQL DATETIME är tz‑lös)
                ts_utc = ts_local.astimezone(pytz.UTC).replace(tzinfo=None)

                try:
                    cursor.execute(
                        "INSERT INTO electricity_prices (datetime, price) VALUES (%s, %s)",
                        (ts_utc, price)
                    )
                    logging.info(
                        f"💾 Sparat: {ts_local.isoformat()} (UTC {ts_utc.strftime('%Y-%m-%d %H:%M:%S')}) => {price} kr/kWh"
                    )
                    saved += 1
                except pymysql.err.IntegrityError:
                    logging.info(f"⏩ Skippad (fanns redan): UTC {ts_utc.strftime('%Y-%m-%d %H:%M:%S')}")

        conn.commit()

    # Informationslogg vid 23/25 timmar (DST)
    if saved in (23, 25):
        if saved == 23:
            logging.info("☀️ Sommartidstart: 23 timmar sparade – OK.")
        else:
            logging.info("🍁 Sommartidslut: 25 timmar sparade – OK.")

    return saved

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datum", help="Datum i formatet ÅÅÅÅ-MM-DD (lokalt dygn)")
    args = parser.parse_args()

    logging.info("==> spotpris.py startade")
    date_str = args.datum or datetime.now(STH).strftime("%Y-%m-%d")

    try:
        target_date_local = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        logging.error("❌ Ogiltigt datumformat. Använd ÅÅÅÅ-MM-DD.")
        return

    data = fetch_prices(target_date_local)
    saved = parse_and_save(data, target_date_local)

    if saved == 0:
        # Fallback: prova gårdagen (ibland publiceras dagens sent)
        fallback_date = target_date_local - timedelta(days=1)
        logging.warning(f"🔁 Försöker med gårdagens data istället: {fallback_date.strftime('%Y-%m-%d')}")
        data = fetch_prices(fallback_date)
        saved = parse_and_save(data, fallback_date)

    logging.info(f"✅ {saved} priser sparade.")
    logging.info("==> spotpris.py klar")

if __name__ == "__main__":
    main()
