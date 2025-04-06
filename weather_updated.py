
import requests
import json
import pymysql
from datetime import datetime
import time
import logging

LAT = 63.8258
LON = 20.2630
API_URL = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={LAT}&lon={LON}"
USER_AGENT = "SmartStyrningApp/1.0 runerova@example.com"

logging.basicConfig(filename='/home/runerova/smartweb/weather_warnings.log', level=logging.WARNING)

def get_connection():
    return pymysql.connect(
        read_default_file="/home/runerova/.my.cnf",
        database="smart_styrning",
        cursorclass=pymysql.cursors.DictCursor
    )

def fetch_weather():
    print("⏳ Hämtar väderdata från MET...")
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(API_URL, headers=headers)
    response.raise_for_status()
    data = response.json()
    print("✅ Data mottagen!")

    observations = []
    for entry in data["properties"]["timeseries"]:
        dt = datetime.fromisoformat(entry["time"].replace("Z", "+00:00"))
        instant = entry["data"]["instant"]["details"]
        temp = instant.get("air_temperature")
        wind = instant.get("wind_speed")

        symbol = ""
        if "next_1_hours" not in entry["data"]:
            logging.warning(f"[{dt}] next_1_hours saknas helt")
        elif "summary" not in entry["data"]["next_1_hours"]:
            logging.warning(f"[{dt}] summary saknas i next_1_hours")
        elif "symbol_code" not in entry["data"]["next_1_hours"]["summary"]:
            logging.warning(f"[{dt}] symbol_code saknas i summary")
        else:
            symbol = entry["data"]["next_1_hours"]["summary"].get("symbol_code", "")
            if not symbol:
                logging.warning(f"[{dt}] symbol_code är tom sträng")

        if temp is None or wind is None:
            continue  # hoppa över rader med ofullständig data

        observations.append((dt, temp, wind, symbol))

    return observations

def save_to_db(data):
    conn = get_connection()
    with conn.cursor() as cursor:
        for dt, temp, wind, symbol in data:
            cursor.execute(
                '''
                INSERT INTO weather (timestamp, temperature, vind, symbol_code)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    temperature=VALUES(temperature),
                    vind=VALUES(vind),
                    symbol_code=VALUES(symbol_code)
                ''',
                (dt, temp, wind, symbol)
            )
    conn.commit()
    print(f"💾 {len(data)} rader sparade.")
    conn.close()

if __name__ == "__main__":
    try:
        data = fetch_weather()
        save_to_db(data)
    except Exception as e:
        print(f"❌ Fel: {e}")
