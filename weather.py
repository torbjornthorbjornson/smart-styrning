
import requests
from datetime import datetime, timedelta
import pytz

from smartweb_backend.db.weather_repo import upsert_weather_rows

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
        dt_utc_naive = (
            datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=pytz.utc)
            .astimezone(pytz.utc)
            .replace(tzinfo=None)
        )
        instant = entry["data"]["instant"]["details"]
        temp = instant.get("air_temperature")
        wind = instant.get("wind_speed")
        symbol = (
            entry["data"].get("next_1_hours", {}).get("summary", {}).get("symbol_code")
            or entry["data"].get("next_6_hours", {}).get("summary", {}).get("symbol_code")
            or entry["data"].get("next_12_hours", {}).get("summary", {}).get("symbol_code")
            or "na"
      )


        weather_data.append({
            "timestamp": dt_utc_naive,
            "temperature": temp,
            "vind": wind,
            "symbol_code": symbol,
        })

    return weather_data

def save_to_database(weather_data):
    upsert_weather_rows(weather_data, city="Alafors")
    for row in weather_data:
        print(f"💾 Sparad eller uppdaterad: {row['timestamp'].isoformat()} ({row['symbol_code']})")

if __name__ == "__main__":
    weather_data = fetch_weather_data()
    save_to_database(weather_data)
