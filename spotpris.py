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
    """
    Spara priser i UTC-naiv tid.
    target_date_local är en date (YYYY-MM-DD).
    Endast poster som ligger inom [midnatt, nästa midnatt) i svensk tid sparas.
    """
    if not data:
        return 0
    saved = 0
    conn = pymysql.connect(**DB_CONFIG)
    with conn:
        with conn.cursor() as cursor:
            cursor.execute("SET time_zone = 'UTC'")

            # Bygg intervallet för hela svenska dygnet
            day_start_local = STHLM.localize(datetime.combine(target_date_local, time(0,0)))
            day_end_local = day_start_local + timedelta(days=1)

            for row in data:
                ts_str = row.get("time_start")
                if not ts_str:
                    continue
                ts_parsed = datetime.fromisoformat(ts_str)  # ofta med +02:00
                if ts_parsed.tzinfo is None:
                    ts_local = STHLM.localize(ts_parsed)
                else:
                    ts_local = ts_parsed.astimezone(STHLM)

                # Kolla att timmen ligger inom rätt dygn
                if not (day_start_local <= ts_local < day_end_local):
                    logging.info(f"⏩ Skippad (utanför dygn): {ts_local}")
                    continue

                # Konvertera till UTC-naiv innan INSERT
                ts_utc_naive = ts_local.astimezone(UTC).replace(tzinfo=None)

                price = row.get("SEK_per_kWh")
                if price is None:
                    continue

                try:
                    cursor.execute(
                        "INSERT INTO electricity_prices (datetime, price) VALUES (%s, %s)",
                        (ts_utc_naive, price),
