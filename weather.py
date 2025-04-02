
import requests
import pymysql
from datetime import datetime

LAT, LON = 57.9005, 12.0735
URL = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={LAT}&lon={LON}"
HEADERS = {"User-Agent": "RaspberryPi-WeatherApp"}

# === DATABAS ===
db_config = {
    'host': 'localhost',
    'user': 'runerova',
    'password': '5675',
    'db': 'weatherdb'
}

def get_weather_forecast():
    response = requests.get(URL, headers=HEADERS)
    data = response.json()
    from datetime import date

    today_str = date.today().strftime('%Y-%m-%d')
    forecasts = [
        f for f in data["properties"]["timeseries"]
        if f["time"].startswith(today_str)
    ]
    forecast_data = {}
    for f in forecasts:
        time = f["time"]
        temp = f["data"]["instant"]["details"]["air_temperature"]
        wind = f["data"]["instant"]["details"].get("wind_speed", None)
        symbol_code = f["data"].get("next_1_hours", {}).get("summary", {}).get("symbol_code", None)
        forecast_data[time] = {"temperature": temp, "wind": wind, "symbol_code": symbol_code}
    return forecast_data

def store_to_database(data):
    connection = pymysql.connect(**db_config)
    with connection.cursor() as cursor:
        for time_str, values in data.items():
            time_obj = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            sql_check = "SELECT COUNT(*) FROM weather WHERE timestamp = %s"
            cursor.execute(sql_check, (time_obj,))
            result = cursor.fetchone()
            if result[0] == 0:
                sql = """
                    INSERT INTO weather (city, temperature, observation_time, timestamp, vind, symbol_code)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    "Alafors",
                    values["temperature"],
                    time_obj,
                    time_obj,
                    values["wind"],
                    values["symbol_code"]
                ))
            else:
                print(f"⏩ Skippad (fanns redan): {time_obj}")
    connection.commit()
    connection.close()

if __name__ == "__main__":
    forecast = get_weather_forecast()
    store_to_database(forecast)
    for time, values in forecast.items():
        print(f"{time}: {values['temperature']}°C, Vind: {values['wind']} m/s, Symbol: {values['symbol_code']}")
