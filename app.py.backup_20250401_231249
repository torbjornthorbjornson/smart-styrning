from flask import Flask, render_template, request, jsonify
import mysql.connector
import json
from datetime import datetime, timedelta

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(
        option_files='/home/runerova/.my.cnf',
        database='smart_styrning'
    )

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/vision")
def vision():
    return render_template("vision.html")

@app.route("/dokumentation")
def dokumentation():
    return render_template("dokumentation.html")

@app.route("/gitlog")
def gitlog():
    try:
        with open("/home/runerova/smartweb/git_backup.log", "r") as f:
            log_content = f.read()
    except FileNotFoundError:
        log_content = "Loggfilen hittades inte."
    return render_template("gitlog.html", log=log_content)

@app.route("/elprisvader")
def elprisvader():
    selected_date_str = request.args.get('datum')
    try:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        selected_date = datetime.now().date()

    tomorrow_date = selected_date + timedelta(days=1)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Hämta väderdata
    cursor.execute("SELECT * FROM weather WHERE DATE(timestamp) = %s", (selected_date,))
    weatherdata = cursor.fetchall()

    # Hämta elprisdata
    cursor.execute("SELECT * FROM electricity_prices WHERE DATE(datetime) = %s", (tomorrow_date,))
    elprisdata = cursor.fetchall()

    # Räkna ut medelvärden
    def average(values):
        return round(sum(values) / len(values), 2) if values else 0

    avg_temp = average([row["temperature"] for row in weatherdata if row.get("temperature") is not None])
    avg_wind = average([row["vind"] for row in weatherdata if row.get("vind") is not None])
    avg_price = average([row["price"] for row in elprisdata if row.get("price") is not None])

    cursor.close()
    conn.close()

    return render_template(
        "elpris_vader.html",
        weatherdata=weatherdata,
        elprisdata=elprisdata,
        avg_temp=avg_temp,
        avg_wind=avg_wind,
        avg_price=avg_price,
        selected_date=selected_date,
        tomorrow_date=tomorrow_date
    )

if __name__ == "__main__":
    app.run(debug=True)
