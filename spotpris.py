
#!/usr/bin/env python3
import requests
import pymysql
import logging
import argparse
import configparser
from datetime import datetime, timedelta, timezone

import pytz

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

# === Läs DB-konto ur ~/.my.cnf ===
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

def fetch_prices(date_obj):
    """Hämtar JSON för en svensk kalenderdag från Elprisetjustnu."""
    area = "SE3"
    date_str = date_obj.strftime("%Y/%m-%d")
    url = f"https://www.elprisetjustnu.se/api/v1/prices/{date_str}_{area}.json"
    logging.info(f"Försöker hämta priser från: {url}")
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        logging.info(f"Dagens priser hämtade: {data[:2]} ...")
        return data
    except Exception as e:
        logging.warning(f"Inga elpriser eller fel: {e}")
        return []

def parse_and_save(data, target_local_date):
    """
    Filtrerar raderna till svensk kalenderdag och sparar som UTC i DB.
    DB-fältet electricity_prices.datetime är naiv DATETIME (tolkas som UTC).
    """
    if not data:
        return 0

    saved = 0
    conn = pymysql.connect(**DB_CONFIG)
    with conn:
        with conn.cursor() as cur:
            for row in data:
                ts_str = row.get("time_start")
                if not ts_str:
                    continue

                # 1) Tiden i JSON är offset-aware lokal tid (+01/+02).
                try:
                    ts_local = datetime.fromisoformat(ts_str)  # ex: '2025-08-28T00:00:00+02:00'
                except Exception:
                    logging.warning(f"Kunde inte tolka time_start: {ts_str}")
                    continue

                # 2) Filtrera på exakt svensk kalenderdag
                if ts_local.astimezone(STHLM).date() != target_local_date.date():
                    logging.info(f"⏩ Skippad (fel datum): {ts_local}")
                    continue

                # 3) Konvertera till UTC-naiv för lagring
                ts_utc = ts_local.astimezone(timezone.utc).replace(tzinfo=None)

                price = row.get("SEK_per_kWh")
                if price is None:
                    continue

                try:
                    cur.execute(
                        "INSERT INTO electricity_prices (datetime, price) VALUES (%s, %s)",
                        (ts_utc, price)
                    )
                    saved += 1
                    logging.info(
                        f"💾 Sparat: lokal {ts_local.strftime('%Y-%m-%d %H:%M %z')} "
                        f"=> UTC {ts_utc.strftime('%Y-%m-%d %H:%M')} => {price} kr/kWh"
                    )
                except pymysql.err.IntegrityError:
                    logging.info(f"⏩ Skippad (fanns redan): UTC {ts_utc.strftime('%Y-%m-%d %H:%M')}")

        conn.commit()

    # Informationslogg vid 23/25 timmar vid DST
    if saved in (23, 25):
        logging.info(f"⏱️ DST-dygn: {saved} timmar sparade – OK.")
    elif saved != 24:
        logging.warning(f"⚠️ Ovänat antal timmar sparade: {saved}")

    return saved

def main():
    logging.info("==> spotpris.py startade")

    parser = argparse.ArgumentParser()
    parser.add_argument("--datum", help="Datum i formatet ÅÅÅÅ-MM-DD")
    args = parser.parse_args()

    # Valt lokalt datum i Sverige
    date_str = args.datum or datetime.now(STHLM).strftime("%Y-%m-%d")
    try:
        target_local = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=None)
        target_local = STHLM.localize(datetime(target_local.year, target_local.month, target_local.day, 0, 0, 0))
    except ValueError:
        logging.error("❌ Ogiltigt datumformat. Använd ÅÅÅÅ-MM-DD.")
        return

    data = fetch_prices(target_local)
    saved = parse_and_save(data, target_local)

    # Fallback: prova gårdagen om dagens gav 0
    if saved == 0:
        fallback_local = (target_local - timedelta(days=1))
        logging.warning(f"🔁 Försöker med gårdagens data: {fallback_local.strftime('%Y-%m-%d')}")
        data = fetch_prices(fallback_local)
        saved = parse_and_save(data, fallback_local)

    logging.info(f"✅ {saved} priser sparade.")
    logging.info("==> spotpris.py klar")

if __name__ == "__main__":
    main()
