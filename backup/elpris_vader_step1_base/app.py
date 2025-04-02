from flask import Flask, render_template, request
import mysql.connector
from datetime import datetime

app = Flask(__name__)

def get_weather_data(date):
    try:
        conn = mysql.connector.connect(option_files='/home/runerova/.my.cnf', database='smart_styrning')
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM weather WHERE DATE(timestamp) = %s ORDER BY timestamp", (date,))
        data = cursor.fetchall()
        conn.close()
        return data
    except Exception as e:
        print("Fel vid hämtning av väderdata:", e)
        return []

@app.route("/")
@app.route("/home")
def home():
    return render_template("home.html")

@app.route("/vision")
def vision():
    return render_template("vision.html")

@app.route("/gitlog")
def gitlog():
    return render_template("gitlog.html")

@app.route("/dokumentation")
def dokumentation():
    return render_template("dokumentation.html")

@app.route("/elprisvader")
def elprisvader():
    selected_date = request.args.get("datum") or datetime.now().strftime("%Y-%m-%d")
    weather_data = get_weather_data(selected_date)
    return render_template("elpris_vader.html", selected_date=selected_date, weatherdata=weather_data)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)