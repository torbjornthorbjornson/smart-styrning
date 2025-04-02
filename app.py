
from flask import Flask, render_template, request
import pymysql
from datetime import datetime, timedelta

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
    return render_template("gitlog.html")

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
            query = '''
                SELECT *
                FROM weather
                WHERE timestamp >= %s AND timestamp < DATE_ADD(%s, INTERVAL 1 DAY)
                ORDER BY timestamp
            '''
            cursor.execute(query, (selected_date, selected_date))
            weather_data = cursor.fetchall()

        labels = [row["timestamp"].strftime("%H:%M") for row in weather_data]
        temperature = [row["temperature"] for row in weather_data]
        vind = [row["vind"] for row in weather_data]

        return render_template("elpris_vader.html",
                               selected_date=selected_date,
                               weatherdata=weather_data,
                               labels=labels,
                               temperature=temperature,
                               vind=vind)

    except Exception as e:
        return f"Fel vid hämtning av data: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
