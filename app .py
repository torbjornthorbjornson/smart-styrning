
from flask import Flask, render_template, request
from datetime import datetime, timedelta
import pymysql
import statistics

app = Flask(__name__)

def get_db_connection():
    return pymysql.connect(
        read_default_file='/home/runerova/.my.cnf',
        database='smart_styrning',
        cursorclass=pymysql.cursors.DictCursor
    )

def get_weather_data(selected_date):
    start = datetime.combine(selected_date, datetime.min.time())
    end = start + timedelta(days=1)
    query = '''
        SELECT *
        FROM weather
        WHERE timestamp >= %s AND timestamp < %s
        ORDER BY timestamp
    '''
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (start, end))
            return cursor.fetchall()

def get_elpris_data(selected_date):
    utc_start = selected_date - timedelta(hours=2)
    utc_end = utc_start + timedelta(days=1)
    query = '''
        SELECT *
        FROM electricity_prices
        WHERE datetime >= %s AND datetime < %s
        ORDER BY datetime
    '''
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (utc_start, utc_end))
            return cursor.fetchall()

@app.route("/")
def home():
    return "<h1>Välkommen!</h1><p>Gå till <a href='/elprisvader'>Elpris & Väder</a></p>"

@app.route("/elprisvader")
def elprisvader():
    datum_str = request.args.get("datum")
    if datum_str:
        selected_date = datetime.strptime(datum_str, "%Y-%m-%d").date()
    else:
        selected_date = datetime.utcnow().date()

    weatherdata = get_weather_data(selected_date)
    elprisdata = get_elpris_data(selected_date)

    try:
        medel_temp = round(statistics.mean([row["temperature"] for row in weatherdata if row["temperature"] is not None]), 1)
    except:
        medel_temp = "?"
    try:
        medel_vind = round(statistics.mean([row["vind"] for row in weatherdata if row["vind"] is not None]), 1)
    except:
        medel_vind = "?"
    try:
        medel_elpris = round(statistics.mean([row["price"] for row in elprisdata if row["price"] is not None]), 3)
    except:
        medel_elpris = "?"

    return render_template(
        "elpris_vader.html",
        selected_date=selected_date,
        weatherdata=weatherdata,
        elprisdata=elprisdata,
        medel_temp=medel_temp,
        medel_vind=medel_vind,
        medel_elpris=medel_elpris
    )

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
