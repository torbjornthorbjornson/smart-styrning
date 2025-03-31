from flask import Flask, render_template, request
import mysql.connector
from datetime import datetime

app = Flask(__name__)

def get_weather_data(date):
    try:
        conn = mysql.connector.connect(option_files='/home/runerova/.my.cnf', database='weatherdb')
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM weather
            WHERE DATE(timestamp) = %s
            ORDER BY timestamp
        """, (date,))
        data = cursor.fetchall()
        conn.close()
        return data
    except Exception as e:
        print("Fel vid hämtning av väderdata:", e)
        return []

def get_electricity_prices(date):
    try:
        conn = mysql.connector.connect(option_files='/home/runerova/.my.cnf', database='weatherdb')
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM electricity_prices
            WHERE DATE(datetime) = %s
            ORDER BY datetime
        """, (date,))
        data = cursor.fetchall()
        conn.close()
        return data
    except Exception as e:
        print("Fel vid hämtning av elprisdata:", e)
        return []

def calculate_averages(weatherdata, electricity_prices):
    avg_temp = round(sum(d['temperature'] for d in weatherdata if d['temperature'] is not None) / len(weatherdata), 1) if weatherdata else None
    avg_wind = round(sum(d['vind'] for d in weatherdata if d['vind'] is not None) / len(weatherdata), 1) if weatherdata else None
    avg_price = round(sum(p['price'] for p in electricity_prices if p['price'] is not None) / len(electricity_prices), 2) if electricity_prices else None
    return avg_temp, avg_wind, avg_price

@app.route("/")
def index():
    selected_date = request.args.get('datum') or datetime.now().strftime('%Y-%m-%d')
    weather_data = get_weather_data(selected_date)
    electricity_prices = get_electricity_prices(selected_date)
    avg_temp, avg_wind, avg_price = calculate_averages(weather_data, electricity_prices)
    return render_template("index.html",
                           weatherdata=weather_data,
                           electricity_prices=electricity_prices,
                           selected_date=selected_date,
                           avg_temp=avg_temp,
                           avg_wind=avg_wind,
                           avg_price=avg_price)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)