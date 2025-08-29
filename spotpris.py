
#!/usr/bin/env python3
import requests
import pymysql
import logging
import argparse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import configparser

# === Logging ===
logging.basicConfig(
    filename='/home/runerova/smartweb/spotpris_info.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
err_handler = logging.FileHandler('/home/runerova/smartweb/spotpris_error.log')
err_handler.setLevel(logging.ERROR)
err_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logging.getLogger().addHandler(err_handler)

# === DB via ~/.my.cnf ===
def read_db_config():
    cfg = configparser.ConfigParser()
    cfg.read('/home/runerova/.my.cnf')
    return dict(
        host='localhost',
        user=cfg['client']['user'],
        password=cfg['client']['password'],
        database='smart_styrning',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
    )

DB = read_db_config()
STHLM = ZoneInfo("Europe/Stockholm")
UTC = timezone.utc

def fetch_prices(local_date):
    area = "SE3"
    url = f"https://www.elprisetjustnu.se/api/v1/prices/{local_date.strftime('%Y/%m-%d')}_{area}.json"
    logging.info(f"Försöker hämta priser från: {url}")
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        logging.info(f"Dagens priser hämtade framgångsrikt: {data[:2]} ...")
        return data
    except Exception as e:
        logging.warning(f"Inga elpriser tillgängliga eller fel uppstod: {e}")
        return []

def parse_and_save(data, target_local_date):
    """Spara alltid som UTC-naiv i MariaDB (DATETIME)."""
    if not data:
        return 0

    saved = 0
    conn = pymysql.connect(**DB)
    with conn:
        with conn.cursor() as cur:
            for row in data:
                ts_str = row.get("time_start")
                price = row.get("SEK_per_kWh")
                if not ts_str or price is None:
                    continue

                # API ger lokal svensk tid med offset (+01/+02)
                ts_local_aw = datetime.fromisoformat(ts_str)  # tz-aware
                # Spara ENBART om datumdelen matchar vald svenska dag
                if ts_local_aw.astimezone(STHLM).date() != target_local_date.date():
                    continue

                ts_utc_naive = ts_local_aw.astimezone(UTC).replace(tzinfo=None)

                try:
                    cur.execute(
                        "INSERT INTO electricity_prices (datetime, price) VALUES (%s, %s)",
                        (ts_utc_naive, float(price)),
                    )
                    logging.info(f"💾 Sparat: {ts_local_aw.isoformat()} ({ts_utc_naive} UTC) => {price} kr/kWh")
                    saved += 1
                except pymysql.err.IntegrityError:
                    logging.info(f"⏩ Skippad (fanns redan): {ts_utc_naive}")

        conn.commit()

    # Informationslogg för 23/25h-dygn
    if saved in (23, 25):
        logging.info(f"ℹ️ Ovanligt antal timmar ({saved}) för {target_local_date.date()} — DST-söndag.")
    return saved

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datum", help="Datum i formatet ÅÅÅÅ-MM-DD (svensk dag)")
    args = parser.parse_args()

    logging.info("==> spotpris.py startade")
    date_str = args.datum or datetime.now(STHLM).strftime("%Y-%m-%d")
    try:
        target_local_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        logging.error("❌ Ogiltigt datumformat. Använd ÅÅÅÅ-MM-DD.")
        return

    data = fetch_prices(target_local_date)
    saved = parse_and_save(data, target_local_date)

    if saved == 0:
        fallback_date = target_local_date - timedelta(days=1)
        logging.warning(f"🔁 Försöker med gårdagens data istället: {fallback_date.strftime('%Y-%m-%d')}")
        data = fetch_prices(fallback_date)
        saved = parse_and_save(data, fallback_date)

    logging.info(f"✅ {saved} priser sparade.")
    logging.info("==> spotpris.py klar")

if __name__ == "__main__":
    main()
