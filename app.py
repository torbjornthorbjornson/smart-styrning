from flask import Flask, render_template, request
import mysql.connector
from datetime import datetime
import os

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(option_files='/home/runerova/.my.cnf', database='smart_styrning')

@app.route("/elprisvader")
def elprisvader():
    selected_date = request.args.get('datum', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM weather WHERE DATE(timestamp) = %s ORDER BY timestamp", (selected_date,))
    weather_data = cursor.fetchall()
    cursor.close()
    conn.close()

    for row in weather_data:
        row['tid_label'] = row['timestamp'].strftime('%H')  # timme som sträng

    return render_template("elpris_vader.html", selected_date=selected_date, weatherdata=weather_data)