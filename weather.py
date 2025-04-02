
import requests
import pymysql
import configparser
from datetime import datetime, timedelta
import pytz

# Läser användare/lösenord från ~/.my.cnf
def get_db_config():
    config = configparser.ConfigParser()
    config.read("/home/runerova/.my.cnf")
    return {
        "host": "localhost",
        "user": config["client"]["user"],
        "password": config["client"]["password"],
        "database": "smart_styrning",
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor
    }

LATITUDE = 57.9
LONGITUDE = 12.1

def fetch_weather_data():
    url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={LATITUDE}&lon={LONGITUDE}"
    headers = {
        "User-Agent": "smart-fastighetsstyrning/1.0 runerova@raspberrypi.local"
    }
    print("🔄 Hämtar väderdata från MET API...")
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    timeseries = data["properties"]["timeseries"]
    weather_data = []

    for entry in timeseries:
        time_str = entry["time"]
        dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
        instant = entry["data"]["instant"]["details"]
        temp = instant.get("air_temperature")
        wind = instant.get("wind_speed")
        symbol = entry["data"].get("next_1_hours", {}).get("summary", {}).get("symbol_code", "")

        weather_data.append({
            "timestamp": dt,
            "temperature": temp,
            "vind": wind,
            "symbol_code": symbol,
        })

    return weather_data

def save_to_database(weather_data):
    db_config = get_db_config()
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()

    for row in weather_data:
        cursor.execute("""
            SELECT id FROM weather WHERE timestamp = %s
        """, (row["timestamp"],))
        if cursor.fetchone():
            print(f"⏩ Skippad (fanns redan): {row['timestamp']}")
            continue

        cursor.execute("""
            INSERT INTO weather (city, temperature, vind, timestamp, observation_time, symbol_code)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            "Alafors",
            row["temperature"],
            row["vind"],
            row["timestamp"],
            row["timestamp"],
            row["symbol_code"]
        ))

        print(f"{row['timestamp'].isoformat()}: {row['temperature']}°C, Vind: {row['vind']} m/s, Symbol: {row['symbol_code']}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    weather_data = fetch_weather_data()
    save_to_database(weather_data)
