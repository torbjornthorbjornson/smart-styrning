
from flask import Flask, render_template, request
import pymysql
from datetime import datetime, timedelta
import statistics

app = Flask(__name__)

# Registrera datumformatfilter för Jinja2
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%H:%M'):
    return value.strftime(format)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/dokumentation')
def dokumentation():
    return render_template('dokumentation.html')

@app.route('/elprisvader')
def elprisvader():
    try:
        # Anslut till databasen
        connection = pymysql.connect(read_default_file='/home/runerova/.my.cnf', database='smart_styrning')
        cursor = connection.cursor()

        # Hämta valt datum från querystring eller använd dagens datum
        selected_date = request.args.get('datum')
        if selected_date:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
        else:
            date_obj = datetime.utcnow()

        # Hämta väderdata för dygnet i UTC
        cursor.execute("""
            SELECT timestamp, temperature, vind, symbol_code
            FROM weather
            WHERE timestamp >= %s AND timestamp < DATE_ADD(%s, INTERVAL 1 DAY)
            ORDER BY timestamp
        """, (date_obj.strftime('%Y-%m-%d'), date_obj.strftime('%Y-%m-%d')))
        weather_rows = cursor.fetchall()

        # Skapa väderstruktur: exakt en post per timme (00–23)
        weather_by_hour = {}
        for row in weather_rows:
            hour = row[0].hour
            weather_by_hour[hour] = row

        full_weather_data = []
        for h in range(24):
            if h in weather_by_hour:
                full_weather_data.append(weather_by_hour[h])
            else:
                full_weather_data.append((datetime(date_obj.year, date_obj.month, date_obj.day, h), None, None, None))

        # Medelvärden (ignorera None)
        temps = [r[1] for r in full_weather_data if r[1] is not None]
        winds = [r[2] for r in full_weather_data if r[2] is not None]
        mean_temp = round(statistics.mean(temps), 1) if temps else None
        mean_wind = round(statistics.mean(winds), 1) if winds else None

        # Hämta elprisdata
        cursor.execute("""
            SELECT datetime, price
            FROM electricity_prices
            WHERE datetime >= %s AND datetime < DATE_ADD(%s, INTERVAL 1 DAY)
            ORDER BY datetime
        """, (date_obj.strftime('%Y-%m-%d'), date_obj.strftime('%Y-%m-%d')))
        price_rows = cursor.fetchall()

        # Medelpris
        prices = [p[1] for p in price_rows if p[1] is not None]
        mean_price = round(statistics.mean(prices), 1) if prices else None

        return render_template(
            'elpris_vader.html',
            weatherdata=full_weather_data,
            pricedata=price_rows,
            mean_temp=mean_temp,
            mean_wind=mean_wind,
            mean_price=mean_price,
            datum=date_obj.strftime('%Y-%m-%d')
        )

    except Exception as e:
        return f"<p>Fel vid hämtning av data: {e}</p>"
    finally:
        if 'connection' in locals():
            connection.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
