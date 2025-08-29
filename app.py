from flask import Flask, render_template, url_for, request, redirect
import pymysql
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo
import subprocess
import os
import math

app = Flask(__name__)

# --- Tidszoner ---
STHLM = ZoneInfo("Europe/Stockholm")
UTC = timezone.utc

def get_connection():
    return pymysql.connect(
        read_default_file="/home/runerova/.my.cnf",
        database="smart_styrning",
        cursorclass=pymysql.cursors.DictCursor
    )

# Hjälpare: svensk dags fönster i UTC (naiva för MariaDB DATETIME)
def stockholm_day_to_utc_window(local_date):
    start_local = datetime.combine(local_date, time.min, tzinfo=STHLM)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(UTC).replace(tzinfo=None)
    end_utc = end_local.astimezone(UTC).replace(tzinfo=None)
    return start_utc, end_utc

# Hjälpare: gör UTC-naiv -> etikett i svensk tid
def utc_naive_to_sthlm_label(utc_naive_dt):
    aware = utc_naive_dt.replace(tzinfo=UTC)
    return aware.astimezone(STHLM).strftime("%H:%M")

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/styrning")
def styrning():
    selected_date_str = request.args.get("datum")
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    else:
        # "Idag" i svensk tid
        selected_date = datetime.now(STHLM).date()

    labels = []
    values = []
    gräns = 0
    no_price = False

    try:
        start_utc, end_utc = stockholm_day_to_utc_window(selected_date)

        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT datetime, price
                FROM electricity_prices
                WHERE datetime >= %s AND datetime < %s
                ORDER BY datetime
                """,
                (start_utc, end_utc),
            )
            priser = cursor.fetchall()

        if not priser:
            no_price = True
        else:
            labels = [utc_naive_to_sthlm_label(row["datetime"]) for row in priser]
            values = [float(row["price"]) for row in priser]

            # Tröskel för 4 billigaste timmar
            if len(values) >= 4:
                gräns = sorted(values)[3]
            else:
                gräns = min(values, default=0)

        return render_template(
            "styrning.html",
            selected_date=selected_date,
            labels=labels,
            values=values,
            gräns=gräns,
            no_price=no_price,
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
            tag_data.append({"name": tag, "message": message, "date": date})
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
        selected_date = datetime.now(STHLM).date()

    try:
        start_utc, end_utc = stockholm_day_to_utc_window(selected_date)
        conn = get_connection()
        with conn.cursor() as cursor:
            # VÄDER – lämnat oförändrat (antas lagras med samma lokala/datumlogik som tidigare)
            cursor.execute(
                """
                SELECT * FROM weather
                WHERE timestamp >= %s AND timestamp < DATE_ADD(%s, INTERVAL 1 DAY)
                ORDER BY timestamp
                """,
                (selected_date, selected_date),
            )
            weather_data = cursor.fetchall()
            weather_date = weather_data[0]["timestamp"].date() if weather_data else selected_date

            # ELPRIS – fråga på svensk dags fönster i UTC
            cursor.execute(
                """
                SELECT datetime, price
                FROM electricity_prices
                WHERE datetime >= %s AND datetime < %s
                ORDER BY datetime
                """,
                (start_utc, end_utc),
            )
            elpris_data = cursor.fetchall()

        # Medelvärden
        medel_temperature = round(
            sum(row["temperature"] for row in weather_data) / len(weather_data), 1
        ) if weather_data else "-"

        medel_vind = round(
            sum(row["vind"] for row in weather_data) / len(weather_data), 1
        ) if weather_data else "-"

        medel_elpris = round(
            sum(row["price"] for row in elpris_data) / len(elpris_data), 2
        ) if elpris_data else "-"

        labels = [row["timestamp"].strftime("%H:%M") for row in weather_data]
        temperature = [row["temperature"] for row in weather_data]
        vind = [row["vind"] for row in weather_data]

        elpris_labels = [utc_naive_to_sthlm_label(row["datetime"]) for row in elpris_data]
        elpris_values = [float(row["price"]) for row in elpris_data]

        return render_template(
            "elpris_vader.html",
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
            weather_date=weather_date,
        )

    except Exception as e:
        return f"Fel vid hämtning av väder/elpris: {e}"

@app.route("/create_backup_tag", methods=["POST"])
def create_backup_tag():
    try:
        comment = request.form.get("comment", "").strip()
        now = datetime.now().strftime("%Y%m%d_%H%M")
        tag_name = f"backup_{now}"
        message = f"🔖 Manuell backup {now}" + (f": {comment}" if comment else "")
        subprocess.check_call(["/usr/bin/git", "tag", "-a", tag_name, "-m", message])
        return redirect("/github_versions")
    except Exception as e:
        return f"Fel vid skapande av git-tag: {e}"

@app.route("/restore_version", methods=["POST"])
def restore_version():
    try:
        tag = request.form.get("tag", "").strip()
        if not tag:
            return "Ingen tagg angiven för återställning."
        now = datetime.now().strftime("%Y%m%d_%H%M")
        backup_tag = f"pre_restore_{tag}_{now}"
        subprocess.check_call(["/usr/bin/git", "tag", "-a", backup_tag, "-m", f"Säkerhetskopia före återställning av {tag}"])
        subprocess.check_call(["/usr/bin/git", "reset", "--hard", tag])
        return redirect(url_for("restore_result", tag=tag, backup=backup_tag))
    except Exception as e:
        return f"Fel vid återställning: {e}"

@app.route("/restore_result")
def restore_result():
    tag = request.args.get("tag")
    backup_tag = request.args.get("backup")
    return render_template("restore_result.html", tag=tag, backup_tag=backup_tag)

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
                    "flow_booster": row.get("flow_booster", 0.0),
                }
    finally:
        conn.close()

    return render_template("vattenstyrning.html", data=latest, cos=math.cos, sin=math.sin)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
