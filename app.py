from flask import Flask, render_template, request
import pymysql
from datetime import datetime, timedelta
import subprocess
import os

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

@app.route("/styrning")
def styrning():
    selected_date_str = request.args.get("datum")
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    else:
        selected_date = datetime.utcnow().date()

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT datetime, price FROM electricity_prices
                WHERE datetime >= %s AND datetime < DATE_ADD(%s, INTERVAL 1 DAY)
                ORDER BY datetime
            ''', (selected_date, selected_date))
            priser = cursor.fetchall()

            fallback_used = False
            if not priser:
                fallback_used = True
                selected_date = selected_date - timedelta(days=1)
                cursor.execute('''
                    SELECT datetime, price FROM electricity_prices
                    WHERE datetime >= %s AND datetime < DATE_ADD(%s, INTERVAL 1 DAY)
                    ORDER BY datetime
                ''', (selected_date, selected_date))
                priser = cursor.fetchall()

        labels = [row["datetime"].strftime("%H:%M") for row in priser]
        values = [float(row["price"]) for row in priser]

        if len(values) >= 3:
            sorted_prices = sorted(values)
            gräns = sorted_prices[3]
        else:
            gräns = min(values, default=0)

        return render_template("styrning.html",
                               labels=labels,
                               values=values,
                               gräns=gräns,
                               selected_date=selected_date,
                               fallback_used=fallback_used)

    except Exception as e:
        return f"Fel vid hämtning av elprisdata: {e}"

@app.route("/vision")
def vision():
    return render_template("vision.html")

@app.route("/dokumentation")
def dokumentation():
    return render_template("dokumentation.html")

@app.route("/github_versions")
def github_versions():
    try:
        tags = subprocess.check_output(["git", "tag", "--sort=-creatordate"]).decode().splitlines()
        tag_data = []
        for tag in tags:
            message = subprocess.check_output(["git", "tag", "-n100", tag]).decode().strip()
            date = subprocess.check_output(["git", "log", "-1", "--format=%cd", tag]).decode().strip()
            tag_data.append({
                "name": tag,
                "message": message,
                "date": date
            })
        return render_template("github_versions.html", tags=tag_data)
    except Exception as e:
        return f"Fel vid hämtning av git-taggar: {e}"

@app.route("/gitlog")
def gitlog():
    try:
        logs = subprocess.check_output(
            ["/usr/bin/git", "log", "--pretty=format:%h - %s (%cr)"],
            cwd=os.path.dirname(__file__),
            text=True
        ).splitlines()
    except Exception as e:
        logs = [f"❌ Kunde inte läsa gitlog: {e}"]
    return render_template("gitlog.html", log="\n".join(logs))

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
            cursor.execute("""
                SELECT * FROM weather
                WHERE timestamp >= %s AND timestamp < DATE_ADD(%s, INTERVAL 1 DAY)
                ORDER BY timestamp
            """, (selected_date, selected_date))
            weather_data = cursor.fetchall()

            cursor.execute("""
                SELECT * FROM electricity_prices
                WHERE datetime >= %s AND datetime < DATE_ADD(%s, INTERVAL 1 DAY)
                ORDER BY datetime
            """, (selected_date, selected_date))
            elpris_data = cursor.fetchall()

            fallback_used = False
            if not elpris_data:
                fallback_used = True
                selected_date = selected_date - timedelta(days=1)
                cursor.execute("""
                    SELECT * FROM electricity_prices
                    WHERE datetime >= %s AND datetime < DATE_ADD(%s, INTERVAL 1 DAY)
                    ORDER BY datetime
                """, (selected_date, selected_date))
                elpris_data = cursor.fetchall()

            date_yesterday = selected_date - timedelta(days=1)

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
                               medel_elpris=medel_elpris,
                               fallback_used=fallback_used,
                               date_yesterday=date_yesterday)

    except Exception as e:
        return f"Fel vid hämtning av väderdata: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)