from flask import Flask, render_template, jsonify, request
import mysql.connector
import json
from datetime import datetime, timedelta

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(option_files='/home/runerova/.my.cnf', database='weatherdb')

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/vision")
def vision():
    return render_template("vision.html")

@app.route("/dokumentation")
def dokumentation():
    return render_template("dokumentation.html")

@app.route("/index")
def index():
    selected_date = request.args.get('datum')
    if selected_date:
        date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
    else:
        date_obj = datetime.now().date()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM weather WHERE DATE(timestamp) = %s", (date_obj,))
    weatherdata = cursor.fetchall()

    cursor.execute("SELECT * FROM electricity_prices WHERE DATE(datetime) = %s", (date_obj,))
    elprisdata = cursor.fetchall()

    # Beräkna medelvärden (om data finns)
    avg_temp = round(sum([row['temperature'] for row in weatherdata]) / len(weatherdata), 1) if weatherdata else None
    avg_wind = round(sum([row['vind'] for row in weatherdata]) / len(weatherdata), 1) if weatherdata else None
    avg_price = round(sum([row['price'] for row in elprisdata]) / len(elprisdata), 3) if elprisdata else None

    cursor.close()
    conn.close()

    return render_template(
        "index.html",
        weatherdata=weatherdata,
        elprisdata=elprisdata,
        avg_temp=avg_temp,
        avg_wind=avg_wind,
        avg_price=avg_price,
        selected_date=selected_date or date_obj.strftime('%Y-%m-%d')
    )

if __name__ == "__main__":
    app.run(debug=True)
