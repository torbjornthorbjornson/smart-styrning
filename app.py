from flask import Flask, render_template, request
import pymysql
from datetime import datetime, timedelta
import os

app = Flask(__name__)

def read_db_config():
    config_path = os.path.expanduser('~/.my.cnf')
    config = {}
    with open(config_path) as f:
        for line in f:
            if line.startswith('user'):
                config['user'] = line.strip().split('=')[1]
            elif line.startswith('password'):
                config['password'] = line.strip().split('=')[1]
    return config

def get_weather_data(selected_date):
    config = read_db_config()
    connection = pymysql.connect(
        host='localhost',
        user=config['user'],
        password=config['password'],
        database='smart_styrning',
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            start_date = selected_date
            end_date = selected_date + timedelta(days=1)
            cursor.execute("""
                SELECT * FROM weather
                WHERE timestamp >= %s AND timestamp < %s
                ORDER BY timestamp
            """, (start_date, end_date))
            weather_rows = cursor.fetchall()
    finally:
        connection.close()

    # Skapa en lista med 24 timmar
    full_weather = []
    for hour in range(24):
        match = next((row for row in weather_rows if row['timestamp'].hour == hour), None)
        if match:
            full_weather.append(match)
        else:
            full_weather.append({
                'timestamp': datetime.combine(selected_date, datetime.min.time()) + timedelta(hours=hour),
                'temperature': None,
                'vind': None,
                'symbol_code': 'na'
            })
    return full_weather

def get_electricity_data(selected_date):
    config = read_db_config()
    connection = pymysql.connect(
        host='localhost',
        user=config['user'],
        password=config['password'],
        database='smart_styrning',
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            start_date = selected_date
            end_date = selected_date + timedelta(days=1)
            cursor.execute("""
                SELECT * FROM electricity_prices
                WHERE datetime >= %s AND datetime < %s
                ORDER BY datetime
            """, (start_date, end_date))
            electricity_rows = cursor.fetchall()
    finally:
        connection.close()

    return electricity_rows

@app.route('/elprisvader')
def elpris_vader():
    date_str = request.args.get('date')
    if date_str:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        selected_date = datetime.utcnow().date()

    weather = get_weather_data(selected_date)
    elpriser = get_electricity_data(selected_date)

    # Medelvärden
    temps = [row['temperature'] for row in weather if row['temperature'] is not None]
    winds = [row['vind'] for row in weather if row['vind'] is not None]
    priser = [row['price'] for row in elpriser if row['price'] is not None]

    avg_temp = round(sum(temps)/len(temps), 1) if temps else None
    avg_wind = round(sum(winds)/len(winds), 1) if winds else None
    avg_price = round(sum(priser)/len(priser), 2) if priser else None

    return render_template('elpris_vader.html',
                           weather=weather,
                           elpriser=elpriser,
                           avg_temp=avg_temp,
                           avg_wind=avg_wind,
                           avg_price=avg_price,
                           selected_date=selected_date)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
