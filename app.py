from flask import Flask, render_template, request
import mysql.connector
from datetime import datetime, timedelta

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(option_files='/home/runerova/.my.cnf', database='smart_styrning')

@app.route("/elprisvader")
def elprisvader():
    selected_date = request.args.get('datum', datetime.now().strftime('%Y-%m-%d'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM weather WHERE DATE(timestamp) = %s ORDER BY timestamp", (selected_date,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # Skapa dict med timmar (00–23)
    hour_map = {str(h).zfill(2): {
        'timestamp': f"{selected_date}T{str(h).zfill(2)}:00:00",
        'tid_label': str(h).zfill(2),
        'temperature': None,
        'vind': None,
        'symbol_code': None
    } for h in range(24)}

    for row in rows:
        hour = row['timestamp'].strftime('%H')
        hour_map[hour] = {
            'timestamp': row['timestamp'].isoformat(),
            'tid_label': hour,
            'temperature': row['temperature'],
            'vind': row['vind'],
            'symbol_code': row['symbol_code']
        }

    weather_data = [hour_map[str(h).zfill(2)] for h in range(24)]

    return render_template("elpris_vader.html", selected_date=selected_date, weatherdata=weather_data)
