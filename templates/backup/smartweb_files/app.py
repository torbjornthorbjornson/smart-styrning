from flask import Flask, render_template, request
import mysql.connector
from datetime import datetime

app = Flask(__name__)

def get_weather_data(date):
    try:
        conn = mysql.connector.connect(option_files='/home/runerova/.my.cnf', database='weatherdb')
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM weather WHERE DATE(timestamp) = %s ORDER BY timestamp", (date,))
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
        cursor.execute("SELECT * FROM electricity_prices WHERE DATE(datetime) = %s ORDER BY datetime", (date,))
        data = cursor.fetchall()
        conn.close()
        return data
    except Exception as e:
        print("Fel vid hämtning av elprisdata:", e)
        return []

@app.route("/")
def index():
    selected_date = request.args.get("datum", datetime.now().strftime("%Y-%m-%d"))
    weather_data = get_weather_data(selected_date) or []
    electricity_prices = get_electricity_prices(selected_date) or []
    return render_template("index.html", weatherdata=weather_data, electricity_prices=electricity_prices, selected_date=selected_date)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
