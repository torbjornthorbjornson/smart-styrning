
from flask import Flask, render_template, request
import pymysql
from datetime import datetime, timedelta

app = Flask(__name__)

# Anslutningsinställningar
DB_CONFIG = {
    "host": "localhost",
    "database": "smart_styrning",
    "read_default_file": "/home/runerova/.my.cnf"
}

def get_weather_data(date_utc):
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        query = """
            SELECT * FROM weather
            WHERE timestamp >= %s AND timestamp < DATE_ADD(%s, INTERVAL 1 DAY)
            ORDER BY timestamp
        """
        cursor.execute(query, (date_utc, date_utc))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Fel vid hämtning av väderdata: {e}")
        return []

def get_elpris_data(date_utc):
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        query = """
            SELECT * FROM electricity_prices
            WHERE datetime >= %s AND datetime < DATE_ADD(%s, INTERVAL 1 DAY)
            ORDER BY datetime
        """
        cursor.execute(query, (date_utc, date_utc))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Fel vid hämtning av elprisdata: {e}")
        return []

@app.route("/elprisvader")
def elpris_vader():
    date_str = request.args.get("datum")
    try:
        date_utc = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else datetime.utcnow().date()
    except Exception as e:
        print(f"Felaktigt datumformat: {e}")
        date_utc = datetime.utcnow().date()

    weatherdata = get_weather_data(date_utc)
    elprisdata = get_elpris_data(date_utc)

    # Fyll i saknade timmar med tomma värden (för grafernas skull)
    full_hours = [date_utc + timedelta(hours=i) for i in range(24)]
    weather_by_hour = {row['timestamp'].replace(tzinfo=None).hour: row for row in weatherdata}
    elpris_by_hour = {row['datetime'].replace(tzinfo=None).hour: row for row in elprisdata}

    weatherdata_full = []
    elprisdata_full = []
    for h in range(24):
        w = weather_by_hour.get(h, {"timestamp": datetime.combine(date_utc, datetime.min.time()) + timedelta(hours=h), "temperature": None, "vind": None, "symbol_code": None})
        e = elpris_by_hour.get(h, {"datetime": datetime.combine(date_utc, datetime.min.time()) + timedelta(hours=h), "price": None})
        weatherdata_full.append(w)
        elprisdata_full.append(e)

    return render_template("elpris_vader.html", weatherdata=weatherdata_full, elprisdata=elprisdata_full, datum=date_utc)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
