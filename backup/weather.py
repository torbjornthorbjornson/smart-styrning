
import requests
import pymysql
from datetime import datetime
import pytz

LATITUDE = 57.9
LONGITUDE = 12.1
USER_AGENT = "smart-fastighetsstyrning/1.0 runerova@raspberrypi.local"
DB_CONFIG = {
    "option_files": "/home/runerova/.my.cnf",
    "database": "smart_styrning"
}

def fetch_weather_data():
    url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={LATITUDE}&lon={LONGITUDE}"
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def save_to_database(data):
    timeseries = data["properties"]["timeseries"]
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    for entry in timeseries:
        timestamp_utc = datetime.fromisoformat(entry["time"].replace("Z", "+00:00"))
        temp = entry["data"]["instant"]["details"].get("air_temperature")
        wind = entry["data"]["instant"]["details"].get("wind_speed")
        symbol_code = entry["data"].get("next_1_hours", {}).get("summary", {}).get("symbol_code", "")

        # Kontrollera om posten redan finns
        cursor.execute("SELECT COUNT(*) FROM weather WHERE timestamp = %s", (timestamp_utc,))
        if cursor.fetchone()[0] > 0:
            print(f"⏩ Skippad (fanns redan): {timestamp_utc}")
            continue

        cursor.execute(
            "INSERT INTO weather (city, temperature, observation_time, timestamp, vind, symbol_code) VALUES (%s, %s, %s, %s, %s, %s)",
            ("Alafors", temp, timestamp_utc, timestamp_utc, wind, symbol_code)
        )
        print(f"{timestamp_utc}: {temp}°C, Vind: {wind} m/s, Symbol: {symbol_code}")

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    print("🔄 Hämtar väderdata från MET API...")
    weather_data = fetch_weather_data()
    save_to_database(weather_data)
    print("✅ Klart.")
