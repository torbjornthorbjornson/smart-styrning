from flask import Flask, render_template, url_for, request, redirect
import pymysql
from datetime import datetime, timedelta, time
import subprocess
import os
import math
import pytz  # tidszoner
import json
import urllib.request, urllib.error

app = Flask(__name__)

def get_connection():
    return pymysql.connect(
        read_default_file="/home/runerova/.my.cnf",
        database="smart_styrning",
        cursorclass=pymysql.cursors.DictCursor
    )

# === Tidszoner och hjälpare för "svensk dag" -> UTC-intervall ===
STHLM = pytz.timezone("Europe/Stockholm")
UTC = pytz.UTC

def today_local_date():
    """Idag som svensk kalenderdag (inte UTC)."""
    return datetime.now(UTC).astimezone(STHLM).date()

def local_day_to_utc_window(local_date):
    """Tar ett date-objekt i svensk tid och returnerar (utc_start, utc_end) som naiva UTC-datetimes."""
    local_midnight = STHLM.localize(datetime.combine(local_date, time(0, 0)))
    utc_start = local_midnight.astimezone(UTC).replace(tzinfo=None)
    utc_end = (local_midnight + timedelta(days=1)).astimezone(UTC).replace(tzinfo=None)
    return utc_start, utc_end

def utc_naive_to_local_label(dt_utc_naive):
    """Gör en HH:MM-etikett i svensk tid från en naiv UTC-datetime lagrad i DB."""
    return dt_utc_naive.replace(tzinfo=UTC).astimezone(STHLM).strftime("%H:%M")

# --- Jinja-filter: skriv ut tider i svensk HH:MM ---
@app.template_filter("svtid")
def svtid(dt_utc_naive):
    try:
        return utc_naive_to_local_label(dt_utc_naive)
    except Exception:
        return ""

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/styrning")
def styrning():
    # Datumval: använd alltid svensk kalenderdag som fallback
    selected_date_str = request.args.get("datum")
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    else:
        selected_date = today_local_date()

    # Hur många billigaste timmar som ska markeras (kan ändras via ?n=6)
    try:
        top_n = int(request.args.get("n", "4"))
    except ValueError:
        top_n = 4
    if top_n < 1:
        top_n = 1

    no_price = False
    labels = []
    values = []
    gräns = 0.0  # maxpriset bland de utvalda timmarna (för info/visning)

    try:
        utc_start, utc_end = local_day_to_utc_window(selected_date)

        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT datetime, price FROM electricity_prices
                WHERE datetime >= %s AND datetime < %s
                ORDER BY datetime
            ''', (utc_start, utc_end))
            priser = cursor.fetchall()

        if not priser:
            no_price = True
            selected_idx = []
            bar_colors = []
            selected_labels_chrono = []
            sorted_by_price = []
        else:
            # Konvertera etiketter till svensk tid; säkerställ float-värden
            labels = [utc_naive_to_local_label(row["datetime"]) for row in priser if row.get("price") is not None]
            values = [float(row["price"]) for row in priser if row.get("price") is not None]

            # Bygg (pris, index)-par och sortera stigande efter pris, därefter timindex för stabilitet
            pairs = [(values[i], i) for i in range(len(values))]
            pairs.sort(key=lambda t: (t[0], t[1]))  # (pris, index)

            # Välj exakt N (eller alla om < N)
            N = min(max(top_n, 1), len(pairs))
            chosen = pairs[:N]
            selected_idx = [i for _, i in chosen]
            selected_set = set(selected_idx)

            # Färger till stapeldiagrammet: exakt valda timmar = gröna
            bar_colors = ['green' if i in selected_set else 'blue' for i in range(len(values))]

            # "Tröskel" för info: högsta pris bland de valda
            gräns = max((values[i] for i in selected_idx), default=0.0)

            # Valda timmar i kronologisk ordning (sorterat på ursprungligt index)
            selected_labels_chrono = [labels[i] for i in sorted(selected_idx)]

            # Trappstege billigast->dyrast för visning/tabell
            sorted_by_price = [
                {"label": labels[i], "price": values[i]}
                for (p, i) in pairs
            ]

        return render_template(
            "styrning.html",
            selected_date=selected_date,
            labels=labels,
            values=values,
            gräns=gräns,
            no_price=no_price,
            top_n=top_n,
            selected_labels_chrono=selected_labels_chrono,
            sorted_by_price=sorted_by_price,
            bar_colors=bar_colors
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
    # Datumval: använd alltid svensk kalenderdag som fallback
    selected_date_str = request.args.get("datum")
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    else:
        selected_date = today_local_date()

    try:
        utc_start, utc_end = local_day_to_utc_window(selected_date)

        conn = get_connection()
        with conn.cursor() as cursor:
            # Väder – svensk dag som UTC-intervall
            cursor.execute("""
                SELECT * FROM weather
                WHERE timestamp >= %s AND timestamp < %s
                ORDER BY timestamp
            """, (utc_start, utc_end))
            weather_data = cursor.fetchall()
            weather_date = selected_date

            # Elpris – svensk dag som UTC-intervall
            cursor.execute("""
                SELECT * FROM electricity_prices
                WHERE datetime >= %s AND datetime < %s
                ORDER BY datetime
            """, (utc_start, utc_end))
            elpris_data = cursor.fetchall()

            fallback_used = False
            if not elpris_data:
               elpris_data = []

            # Medelvärden
            medel_temperature = round(sum(row["temperature"] for row in weather_data) / len(weather_data), 1) if weather_data else "-"
            medel_vind        = round(sum(row["vind"]        for row in weather_data) / len(weather_data), 1) if weather_data else "-"
            medel_elpris      = round(sum(row["price"]       for row in elpris_data)  / len(elpris_data),  1) if elpris_data else "-"

            # Etiketter i svensk tid (för graferna)
            labels         = [utc_naive_to_local_label(row["timestamp"]) for row in weather_data]
            temperature    = [row["temperature"] for row in weather_data]
            vind           = [row["vind"]        for row in weather_data]
            elpris_labels  = [utc_naive_to_local_label(row["datetime"])  for row in elpris_data]
            elpris_values  = [row["price"] for row in elpris_data]

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
                               weather_date=weather_date)
        
    except Exception as e:
        return f"Fel vid hämtning av väder/elprisdata: {e}"

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

    return render_template("vattenstyrning.html", data=latest, cos=math.cos, sin=math.sin)
from flask import Response  # högst upp bland imports om inte redan finns

@app.route("/api/exo_payload/<site_code>")
def api_exo_payload(site_code):
    """
    GET /api/exo_payload/<site_code>?day=YYYY-MM-DD&build=1&n=4&cheap_pct=-0.30&exp_pct=0.50

    - day       (valfri): om saknas används svensk kalenderdag (idag).
    - build     (valfri): "1", "true" => bygg payload (kör våra SQL-procedurer) innan hämtning.
    - n         (valfri): topp-N timmar (om saknas används sites.default_topn).
    - cheap_pct (valfri): t.ex. -0.30
    - exp_pct   (valfri): t.ex. 0.50
    """
    day_str = request.args.get("day")
    if day_str:
        try:
            day_local = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            return Response('{"error":"invalid day format, use YYYY-MM-DD"}', status=400, mimetype="application/json")
    else:
        # använd svensk kalenderdag (du har already today_local_date())
        try:
            day_local = today_local_date()
        except Exception:
            # fallback om funktionen saknas
            day_local = datetime.utcnow().date()

    build = str(request.args.get("build", "0")).lower() in ("1", "true", "yes")
    # Optionala parametrar
    n_arg = request.args.get("n")
    cheap_arg = request.args.get("cheap_pct")
    exp_arg = request.args.get("exp_pct")

    try:
        conn = get_connection()
        with conn.cursor() as cur:
            # Hämta site + default_topn
            cur.execute("SELECT site_code, tz, default_topn FROM sites WHERE site_code=%s LIMIT 1", (site_code,))
            site = cur.fetchone()
            if not site:
                return Response('{"error":"unknown site"}', status=404, mimetype="application/json")

            top_n = int(n_arg) if n_arg is not None else int(site["default_topn"])
            cheap_pct = float(cheap_arg) if cheap_arg is not None else -0.30
            exp_pct   = float(exp_arg)   if exp_arg   is not None else  0.50

            if build:
                # Bygg / uppdatera allt för dagen
                cur.execute("CALL exo_build_payload(%s,%s,%s,%s,%s)", (site_code, day_local, top_n, cheap_pct, exp_pct))
                conn.commit()

            # Hämta lagrad payload
            cur.execute(
                "SELECT payload_json FROM exo_payloads WHERE site_code=%s AND day_local=%s",
                (site_code, day_local)
            )
            row = cur.fetchone()

        if row and row.get("payload_json"):
            return Response(row["payload_json"], mimetype="application/json")
        else:
            # Tipsa om att testa build=1
            return Response('{"error":"payload not found for day; try with build=1"}', status=404, mimetype="application/json")

    except Exception as e:
        msg = str(e).replace('"', '\\"')
        return Response(f'{{"error":"{msg}"}}', status=500, mimetype="application/json")
def post_to_exo(payload_json: str, exo_url: str, token: str | None = None, timeout: int = 20):
    """POST:a JSON till EXO. Returnerar (status, body-kort)."""
    data = payload_json.encode("utf-8")
    req = urllib.request.Request(
        exo_url, data=data, method="POST",
        headers={"Content-Type": "application/json"}
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = resp.status
        body = resp.read().decode("utf-8", "ignore")[:2000]
    return status, body

@app.route("/api/exo_push/<site_code>", methods=["GET", "POST"])
def api_exo_push(site_code):
    """
    Skickar EXO-payload för en site+dag till EXO.
    Exempel:
      GET/POST /api/exo_push/C1?day=2025-08-29&build=1&n=4&cheap_pct=-0.30&exp_pct=0.50
      &dry_run=1  (för att bara visa vad som skulle skickas)
      &exo_url=https://arrigo.exempel/api/price  (annars används env EXO_URL)
      &token=hemligt  (annars används env EXO_TOKEN)
    """
    # 1) Parametrar
    day_str = request.args.get("day")
    if day_str:
        try:
            day_local = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            return Response('{"error":"invalid day format, use YYYY-MM-DD"}', status=400, mimetype="application/json")
    else:
        try:
            day_local = today_local_date()
        except Exception:
            day_local = datetime.utcnow().date()

    build = str(request.args.get("build", "0")).lower() in ("1","true","yes","on")
    dry_run = str(request.args.get("dry_run", "0")).lower() in ("1","true","yes","on")
    timeout_sec = int(request.args.get("timeout", "20"))

    n_arg = request.args.get("n")
    cheap_arg = request.args.get("cheap_pct")
    exp_arg = request.args.get("exp_pct")

    exo_url = request.args.get("exo_url") or os.environ.get("EXO_URL")
    token   = request.args.get("token")   or os.environ.get("EXO_TOKEN")
    if not exo_url:
        return Response('{"error":"EXO_URL saknas (ange ?exo_url=... eller sätt env EXO_URL)"}',
                        status=400, mimetype="application/json")

    # 2) Bygg payload i DB (om begärt) och hämta JSON
    payload = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            # Hämta defaults för site
            cur.execute("SELECT site_code, tz, default_topn FROM sites WHERE site_code=%s LIMIT 1", (site_code,))
            site = cur.fetchone()
            if not site:
                return Response('{"error":"unknown site"}', status=404, mimetype="application/json")

            top_n = int(n_arg) if n_arg is not None else int(site["default_topn"])
            cheap_pct = float(cheap_arg) if cheap_arg is not None else -0.30
            exp_pct   = float(exp_arg)   if exp_arg   is not None else  0.50

            if build:
                cur.execute("CALL exo_build_payload(%s,%s,%s,%s,%s)", (site_code, day_local, top_n, cheap_pct, exp_pct))
                conn.commit()

            cur.execute(
                "SELECT payload_json FROM exo_payloads WHERE site_code=%s AND day_local=%s",
                (site_code, day_local)
            )
            row = cur.fetchone()
            if row and row.get("payload_json"):
                payload = row["payload_json"]
    except Exception as e:
        msg = str(e).replace('"', '\\"')
        return Response(f'{{"error":"{msg}"}}', status=500, mimetype="application/json")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not payload:
        return Response('{"error":"payload not found for day; try build=1"}', status=404, mimetype="application/json")

    # 3) Skicka (eller torrkör)
    if dry_run:
        # visa vart vi skulle skicka + payloaden
        return Response(json.dumps({
            "dry_run": True,
            "target": {"exo_url": exo_url, "has_token": bool(token)},
            "payload": json.loads(payload)
        }, ensure_ascii=False), mimetype="application/json")

    try:
        status, body = post_to_exo(payload, exo_url, token, timeout=timeout_sec)
        return Response(json.dumps({
            "sent": True,
            "http_status": status,
            "exo_response": body,
            "site_id": site_code,
            "day": day_local.strftime("%Y-%m-%d")
        }, ensure_ascii=False), mimetype="application/json")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore") if hasattr(e, "read") else ""
        msg = {"sent": False, "http_status": e.code, "error": str(e), "body": body[:2000]}
        return Response(json.dumps(msg, ensure_ascii=False), status=502, mimetype="application/json")
    except Exception as e:
        msg = {"sent": False, "error": str(e)}
        return Response(json.dumps(msg, ensure_ascii=False), status=502, mimetype="application/json")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
