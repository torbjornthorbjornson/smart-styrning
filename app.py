
from flask import Flask, render_template, request
import pymysql
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Register a custom Jinja filter for formatting datetime
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%H:%M'):
    return value.strftime(format)

# Route: startsida
@app.route('/')
def home():
    return render_template('home.html')

# Route: elpris och väder
@app.route('/elprisvader')
def elprisvader():
    try:
        selected_date = request.args.get('date')
        if selected_date:
            selected_date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
        else:
            selected_date_obj = datetime.utcnow()
            selected_date = selected_date_obj.strftime("%Y-%m-%d")

        conn = pymysql.connect(
            host='localhost',
            database='smart_styrning',
            read_default_file=os.path.expanduser("~/.my.cnf")
        )
        cursor = conn.cursor()

        query_weather = """
            SELECT timestamp, temperature, vind, symbol_code 
            FROM weather 
            WHERE timestamp >= %s AND timestamp < DATE_ADD(%s, INTERVAL 1 DAY)
            ORDER BY timestamp
        """
        cursor.execute(query_weather, (selected_date, selected_date))
        weather_rows = cursor.fetchall()

        query_prices = """
            SELECT datetime, price 
            FROM electricity_prices 
            WHERE datetime >= %s AND datetime < DATE_ADD(%s, INTERVAL 1 DAY)
            ORDER BY datetime
        """
        cursor.execute(query_prices, (selected_date, selected_date))
        price_rows = cursor.fetchall()

        cursor.close()
        conn.close()

        weatherdata = [
            {
                "tid": row[0],
                "temperature": row[1],
                "vind": row[2],
                "symbol": row[3]
            }
            for row in weather_rows
        ]

        pricedata = [
            {
                "tid": row[0],
                "pris": row[1]
            }
            for row in price_rows
        ]

        return render_template("elpris_vader.html", weatherdata=weatherdata, pricedata=pricedata, selected_date=selected_date)

    except Exception as e:
        return f"Fel vid hämtning av data: {e}"

# Route: dokumentation
@app.route('/dokumentation')
def dokumentation():
    return render_template('dokumentation.html')

# Route: vision
@app.route('/vision')
def vision():
    return render_template('vision.html')

# Route: gitlog
@app.route('/gitlog')
def gitlog():
    return render_template('gitlog.html')

if __name__ == '__main__':
    app.run(debug=True, port=8000)
