
from flask import Flask, render_template, request
import pymysql
from datetime import datetime, timedelta
import subprocess  # ✅ krävs för gitlog
import os          # ✅ krävs för gitlog

app = Flask(__name__)

def get_connection():
    return pymysql.connect(
        read_default_file="/home/runerova/.my.cnf",
        database="smart_styrning",
        cursorclass=pymysql.cursors.DictCursor
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
        logs = subprocess.check_output(
            ["git", "log", "--pretty=format:%h - %s (%cr)"],
            cwd=os.path.dirname(__file__),
            text=True
        ).splitlines()
    except Exception as e:
        logs = [f"❌ Kunde inte läsa gitlog: {e}"]
    return render_template("gitlog.html", log="\n".join(logs))  # 👈 rätt variabelnamn till gitlog.html

@app.route("/elprisvader")
def elprisvader():
    selected_date_str = request.args.get("datum")
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    else:
        selected_date = datetime.utcnow().date()

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT * FROM weather
                WHERE timestamp >= %s AND timestamp < DATE_ADD(%s, INTERVAL 1 DAY)
                ORDER BY timestamp
            ''', (selected_date, selected_date))
            weather_data = cursor.fetchall()

            cursor.execute('''
                SELECT * FROM electricity_prices
                WHERE datetime >= %s AND datetime < DATE_ADD(%s, INTERVAL 1 DAY)
                ORDER BY datetime
            ''', (selected_date, selected_date))
            elpris_data = cursor.fetchall()

            medel_temperature = round(sum(row["temperature"] for row in weather_data) / len(weather_data), 1) if weather_data else "-"
            medel_vind = round(sum(row["vind"] for row in weather_data) / len(weather_data), 1) if weather_data else "-"
            medel_elpris = round(sum(row["price"] for row in elpris_data) / len(elpris_data), 1) if elpris_data else "-"

            labels = [row["timestamp"].strftime("%H:%M") for row in weather_data]
            temperature = [row["temperature"] for row in weather_data]
            vind = [row["vind"] for row in weather_data]

            elpris_labels = [row["datetime"].strftime("%H:%M") for row in elpris_data]
            elpris_values = [row["price"] for row in elpris_data]

        return render_template("elpris_vader.html",
                               selected_date=selected_date,
                               weatherdata=weather_data,
                               elprisdata=elpris_data,
                               labels=labels,
                               temperature=temperature,
                               vind=vind,
                               elpris_labels=elpris_labels,
                               elpris_values=elpris_values,
                               medel_temperature=medel_temperature,
                               medel_vind=medel_vind,
                               medel_elpris=medel_elpris)

    except Exception as e:
        return f"Fel vid hämtning av data: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
