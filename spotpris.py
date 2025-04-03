
#!/usr/bin/env python3
import requests
import pymysql
import logging
import argparse
from datetime import datetime, timedelta
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

def parse_and_save(data, target_date_utc, target_date):
    if not data:
        return 0
    saved = 0
    conn = pymysql.connect(**DB_CONFIG)
    with conn:
        with conn.cursor() as cursor:
            for row in data:
                timestamp_str = row.get("time_start")
                if not timestamp_str:
                    continue
                timestamp = datetime.fromisoformat(timestamp_str)
                stockholm = pytz.timezone("Europe/Stockholm")
                local_date = timestamp.astimezone(stockholm).date()
                if local_date != target_date.date():
                    print(f"⏩ Skippad: fel datum ({local_date} != {target_date.date()})")
                    logging.info(f"⏩ Skippad: fel datum ({local_date} != {target_date.date()})")
                    continue
                price = row.get("SEK_per_kWh")
                if price is None:
                    continue
                try:
                    cursor.execute(
                        "INSERT INTO electricity_prices (datetime, price) VALUES (%s, %s)",
                        (timestamp, price)
                    )
                    logging.info(f"💾 Sparat: {timestamp} => {price} kr/kWh")
                    saved += 1
                except pymysql.err.IntegrityError:
                    logging.info(f"⏩ Skippad (fanns redan): {timestamp}")
        conn.commit()

    if saved == 23:
        stockholm = pytz.timezone("Europe/Stockholm")
        if stockholm.localize(datetime.combine(target_date.date(), datetime.min.time())).dst():
            print("☀️ Sommartid: Endast 23 timmar – detta är normalt.")
            logging.info("☀️ Sommartid: 23 timmar sparade – OK.")
        else:
            print("⚠️ Bara 23 timmar sparade – men inte sommartid.")
            logging.warning("⚠️ Bara 23 timmar sparade – misstänkt fel.")

    return saved

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datum", help="Datum i formatet ÅÅÅÅ-MM-DD")
    args = parser.parse_args()

    logging.info("==> spotpris.py startade")
    date_str = args.datum or datetime.now().strftime("%Y-%m-%d")
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        logging.error("❌ Ogiltigt datumformat. Använd ÅÅÅÅ-MM-DD.")
        return

    stockholm = pytz.timezone("Europe/Stockholm")
    target_date_utc = stockholm.localize(
        datetime.combine(target_date.date(), datetime.min.time())
    ).astimezone(pytz.UTC)

    data = fetch_prices(target_date)
    saved = parse_and_save(data, target_date_utc, target_date)

    if saved == 0:
        fallback_date = target_date - timedelta(days=1)
        logging.warning(f"🔁 Försöker med gårdagens data istället: {fallback_date}")
        data = fetch_prices(fallback_date)
        saved = parse_and_save(data, fallback_date, fallback_date)

    logging.info(f"✅ {saved} priser sparade.")
    logging.info("==> spotpris.py klar")

if __name__ == "__main__":
    main()