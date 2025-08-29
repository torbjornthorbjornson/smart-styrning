from flask import Flask, render_template, url_for, request, redirect

import pymysql
from datetime import datetime, timedelta, timezone
import subprocess
import os
import math
import pytz
import pytz  # NY
from datetime import datetime, timedelta  # du har redan datetime/timedelta

STHLM = pytz.timezone("Europe/Stockholm")

def utc_window_for_swedish_date(d):
    """Returnera (start_utc, end_utc) för kalenderdag d i svensk tid."""
    start_local = datetime.combine(d, datetime.min.time())
    start_utc = STHLM.localize(start_local).astimezone(pytz.UTC).replace(tzinfo=None)
    end_utc   = STHLM.localize(start_local + timedelta(days=1)).astimezone(pytz.UTC).replace(tzinfo=None)
    return start_utc, end_utc

def to_local_label(utc_dt):
    """Format för etikett i svensk tid från UTC-datetime (naiv)."""
    return pytz.UTC.localize(utc_dt).astimezone(STHLM).strftime("%H:%M")

app = Flask(__name__)

def get_connection():
    return pymysql.connect(
        read_default_file="/home/runerova/.my.cnf",
        database="smart_styrning",
        cursorclass=pymysql.cursors.DictCursor
    )

STHLM = pytz.timezone("Europe/Stockholm")

@app.route("/")
def home():
    return render_template("home.html")

def _local_day_bounds_as_utc(selected_date_str: str | None):
    """
    Tar ett datum (YYYY-MM-DD) i svensk tid, eller 'idag' om None,
    och returnerar (start_utc, end_utc) som naiva UTC-datetimes för SQL.
    """
    if selected_date_str:
        day_local = STHLM.localize(datetime.strptime(selected_date_str, "%Y-%m-%d"))
    else:
        day_local = datetime.now(STHLM).replace(hour=0, minute=0, second=0, microsecond=0)

    start_local = day_local
    end_local = day_local + timedelta(days=1)

    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    return day_local.date(), start_utc, end_utc

def _label_local_from_utc(dt_utc_naive):
    """Gör en snygg HH:MM‑etikett i svensk tid från UTC-naiv datetime från DB."""
    dt_aware = dt_utc_naive.replace(tzinfo=timezone.utc)
    return dt_aware.astimezone(STHLM).strftime("%H:%M")

@app.route("/styrning")
def styrning():
    selected_date_str = request.args.get("datum")
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    else:
        # visa svensk dag som default (inte UTC-dag)
        selected_date = datetime.now(STHLM).date()

    no_price = False
    labels, values = [], []
    gräns = 0

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            start_utc, end_utc = utc_window_for_swedish_date(selected_date)
            cursor.execute("""
                SELECT datetime, price
                FROM electricity_prices
                WHERE datetime >= %s AND datetime < %s
                ORDER BY datetime
            """, (start_utc, end_utc))
            priser = cursor.fetchall()

        if not priser:
            no_price = True
        else:
            labels = [to_local_label(row["datetime"]) for row in priser]
            values = [float(row["price"]) for row in priser]

            if len(values) >= 3:
                gräns = sorted(values)[3]  # dina tidigare regler
            else:
                gräns = min(values, default=0)

        return render_template(
            "styrning.html",
            selected_date=selected_date,
            labels=labels,
            values=values,
            gräns=gräns,
            no_price=no_price
        )

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
        git_path = "/usr/bin/git"
        tags = subprocess.check_output([git_path, "tag", "--sort=-creatordate"]).decode().splitlines()
        tag_data = []
        for tag in tags:
            message = subprocess.check_output([git_path, "tag", "-n100", tag]).decode().strip()
            date = subprocess.check_output([git_path, "log", "-1", "--format=%cd", tag]).decode().strip()
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
    selected_date, start_utc, end_utc = _local_day_bounds_as_utc(selected_date_str)

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Väder – lämnar oförändrat (antag att dina tider redan matchar UI)
            cursor.execute("""
                SELECT * FROM weather
                WHERE timestamp >= %s AND timestamp < %s
                ORDER BY timestamp
            """, (selected_date, selected_date + timedelta(days=1)))
            weather_data = cursor.fetchall()
            weather_date = weather_data[0]["timestamp"].date() if weather_data else selected_date

            # Elpris – hämta efter svensk kalenderdag via UTC-intervall
           # ...efter väder-frågan...
start_utc, end_utc = utc_window_for_swedish_date(selected_date)
cursor.execute("""
    SELECT datetime, price
    FROM electricity_prices
    WHERE datetime >= %s AND datetime < %s
    ORDER BY datetime
""", (start_utc, end_utc))
elpris_data = cursor.fetchall()

elpris_labels = [to_local_label(row["datetime"]) for row in elpris_data]
elpris_values = [row["price"] for row in elpris_data]


            # Medelvärden
            medel_temperature = round(sum(row["temperature"] for row in weather_data) / len(weather_data), 1) if weather_data else "-"
            medel_vind = round(sum(row["vind"] for row in weather_data) / len(weather_data), 1) if weather_data else "-"
            medel_elpris = round(sum(row["price"] for row in elpris_data) / len(elpris_data), 2) if elpris_data else "-"

            # Serier för UI
            labels = [row["timestamp"].strftime("%H:%M") for row in weather_data]
            temperature = [row["temperature"] for row in weather_data]
            vind = [row["vind"] for row in weather_data]
            elpris_labels = [_label_local_from_utc(row["datetime"]) for row in elpris_data]
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
                               fallback_used=False,
                               weather_date=weather_date)

    except Exception as e:
        return f"Fel vid hämtning av väderdata: {e}"

MAX_VOLYM = 10000

@app.route("/vattenstyrning")
def vattenstyrning():
    conn = get_connection()
    latest = {}
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM water_status ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                latest = {
                    "nivå": row["level_liters"],
                    "nivå_procent": round(row["level_liters"] / MAX_VOLYM * 100),
                    "tryck": row["system_pressure"],
                    "p1": row["pump1_freq"],
                    "p2": row["pump2_freq"],
                    "p3": row["pump3_freq"],
                    "booster": row.get("booster_freq", 0.0),
                    "flow_p1": row.get("flow_p1", 0.0),
                    "flow_p2": row.get("flow_p2", 0.0),
                    "flow_p3": row.get("flow_p3", 0.0),
                    "flow_booster": row.get("flow_booster", 0.0)
                }
    finally:
        conn.close()

    return render_template(
        "vattenstyrning.html",
        data=latest,
        cos=math.cos,
        sin=math.sin
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
