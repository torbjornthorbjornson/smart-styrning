from flask import Flask, render_template, url_for, request, redirect
import pymysql
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import subprocess
import os
import math

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
    # --- Datumval (visa lokalt dygn som default) ---
    selected_date_str = request.args.get("datum")
    sth = ZoneInfo("Europe/Stockholm")
    utc = ZoneInfo("UTC")

    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    else:
        selected_date = datetime.now(sth).date()

    # Räkna ut UTC-intervall för det lokala dygnet
    start_local = datetime(selected_date.year, selected_date.month, selected_date.day, 0, 0, tzinfo=sth)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(utc).replace(tzinfo=None)

    no_price = False
    labels = []
    values = []
    gräns = 0

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
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
            # Konvertera varje timme från UTC (naiv) till Stockholm för etiketter
            for row in priser:
                # PyMySQL returnerar naiv datetime -> tolka som UTC
                utc_dt = row["datetime"].replace(tzinfo=utc)
                local_dt = utc_dt.astimezone(sth)
                labels.append(local_dt.strftime("%H:%M"))
                values.append(float(row["price"]))

            # "gräns" = 4:e lägsta priset om det finns >= 4 värden
            if len(values) >= 4:
                gräns = sorted(values)[3]
            else:
                gräns = min(values, default=0.0)

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
    sth = ZoneInfo("Europe/Stockholm")
    utc = ZoneInfo("UTC")

    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    else:
        selected_date = datetime.now(sth).date()

    # UTC-intervall för lokala dygnet (för elpris)
    start_local = datetime(selected_date.year, selected_date.month, selected_date.day, 0, 0, tzinfo=sth)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(utc).replace(tzinfo=None)

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Vädret: lämnar din logik oförändrad (okänt om weather är UTC eller lokalt)
            cursor.execute("""
                SELECT * FROM weather
                WHERE timestamp >= %s AND timestamp < DATE_ADD(%s, INTERVAL 1 DAY)
                ORDER BY timestamp
            """, (selected_date, selected_date))
            weather_data = cursor.fetchall()
            weather_date = weather_data[0]["timestamp"].date() if weather_data else selected_date

            # Elpris: hämta över det lokala dygnet via UTC-intervall
            cursor.execute("""
                SELECT datetime, price
                FROM electricity_prices
                WHERE datetime >= %s AND datetime < %s
                ORDER BY datetime
            """, (start_utc, end_utc))
            elpris_data_rows = cursor.fetchall()

        # Konvertera elpriset till lokal tid för visning
        elpris_data = []
        elpris_labels = []
        elpris_values = []
        for row in elpris_data_rows:
            utc_dt = row["datetime"].replace(tzinfo=utc)
            local_dt = utc_dt.astimezone(sth)
            elpris_data.append({"datetime": local_dt, "price": row["price"]})
            elpris_labels.append(local_dt.strftime("%H:%M"))
            elpris_values.append(row["price"])

        # Medelvärden
        medel_temperature = round(sum(r["temperature"] for r in weather_data) / len(weather_data), 1) if weather_data else "-"
        medel_vind = round(sum(r["vind"] for r in weather_data) / len(weather_data), 1) if weather_data else "-"
        medel_elpris = round(sum(float(r["price"]) for r in elpris_data_rows) / len(elpris_data_rows), 1) if elpris_data_rows else "-"

        return render_template(
            "elpris_vader.html",
            selected_date=selected_date,
            weatherdata=weather_data,
            elprisdata=elpris_data,
            labels=[r["timestamp"].strftime("%H:%M") for r in weather_data],
            temperature=[r["temperature"] for r in weather_data],
            vind=[r["vind"] for r in weather_data],
            elpris_labels=elpris_labels,
            elpris_values=elpris_values,
            medel_temperature=medel_temperature,
            medel_vind=medel_vind,
            medel_elpris=medel_elpris,
            fallback_used=False,
            weather_date=weather_date
        )

    except Exception as e:
        return f"Fel vid hämtning av väder/elnätsdata: {e}"

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
