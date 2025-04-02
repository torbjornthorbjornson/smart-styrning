from flask import Flask, render_template, request
import mysql.connector
from datetime import datetime
import json

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    selected_date = request.args.get("datum", datetime.now().date().isoformat())

    try:
        conn = mysql.connector.connect(option_files='/home/runerova/.my.cnf', database='smartdb')
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM weather WHERE DATE(timestamp) = %s ORDER BY timestamp ASC", (selected_date,))
        weather_rows = cursor.fetchall()
        cursor.close()
    except mysql.connector.Error as e:
        print("Fel vid hämtning av väderdata:", e)
        weather_rows = []

    try:
        conn = mysql.connector.connect(option_files='/home/runerova/.my.cnf', database='smartdb')
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM electricity_prices WHERE DATE(datetime) = %s ORDER BY datetime ASC", (selected_date,))
        electricity_rows = cursor.fetchall()
        cursor.close()
    except mysql.connector.Error as e:
        print("Fel vid hämtning av elprisdata:", e)
        electricity_rows = []

    return render_template("index.html",
                           weatherdata=weather_rows,
                           electricity_prices=electricity_rows,
                           valt_datum=selected_date)

if __name__ == "__main__":
    app.run(debug=True)
