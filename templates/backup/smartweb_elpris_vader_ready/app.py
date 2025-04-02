from flask import Flask, render_template
import mysql.connector
import json
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(option_files='/home/runerova/.my.cnf', database='smart_styrning')

@app.route("/")
def index():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Hämta väderdata (senaste dygnet)
        cursor.execute("""
            SELECT * FROM weather
            WHERE timestamp >= NOW() - INTERVAL 1 DAY
            ORDER BY timestamp
        """)
        weather_data = cursor.fetchall()

        # Hämta elprisdata (senaste dygnet)
        cursor.execute("""
            SELECT * FROM electricity_prices
            WHERE datetime >= NOW() - INTERVAL 1 DAY
            ORDER BY datetime
        """)
        price_data = cursor.fetchall()

        # Konvertera till JSON för graferna
        weather_json = json.dumps(weather_data, default=str)
        price_json = json.dumps(price_data, default=str)

        # Medelvärden
        avg_temp = round(sum([w['temperature'] for w in weather_data]) / len(weather_data), 1) if weather_data else None
        avg_wind = round(sum([w['wind_speed'] for w in weather_data]) / len(weather_data), 1) if weather_data else None
        avg_price = round(sum([p['price'] for p in price_data]) / len(price_data), 3) if price_data else None

        return render_template("elpris_vader.html",
                               weather_data=weather_data,
                               price_data=price_data,
                               weather_json=weather_json,
                               price_json=price_json,
                               avg_temp=avg_temp,
                               avg_wind=avg_wind,
                               avg_price=avg_price)

    except Exception as e:
        return f"Fel vid databasanslutning: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
