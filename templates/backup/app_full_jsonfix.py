from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://runerova:5675@localhost/weatherdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class ElectricityPrice(db.Model):
    __tablename__ = 'electricity_prices'
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime)
    price = db.Column(db.Float)

class Weather(db.Model):
    __tablename__ = 'weather'
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(255))
    temperature = db.Column(db.Float)
    observation_time = db.Column(db.DateTime)
    timestamp = db.Column(db.DateTime)
    vind = db.Column(db.Float)
    symbol_code = db.Column(db.String(50))

@app.route("/", methods=["GET"])
def index():
    selected_date = request.args.get('datum', datetime.now().date().isoformat())

    # Elpriser
    elpriser_raw = ElectricityPrice.query.filter(
        db.func.date(ElectricityPrice.datetime) == selected_date
    ).order_by(ElectricityPrice.datetime.asc()).all()

    elpriser = [
        {
            "datetime": row.datetime.strftime("%Y-%m-%d %H:%M"),
            "price": row.price
        }
        for row in elpriser_raw
    ]

    # Väderdata
    weatherdata_raw = Weather.query.filter(
        db.func.date(Weather.timestamp) == selected_date
    ).order_by(Weather.timestamp.asc()).all()

    weatherdata = [
        {
            "timestamp": row.timestamp.strftime("%Y-%m-%d %H:%M"),
            "temperature": row.temperature,
            "vind": row.vind,
            "symbol_code": row.symbol_code
        }
        for row in weatherdata_raw
    ]

    return render_template(
        "index.html",
        elpriser=elpriser,
        weatherdata=weatherdata,
        valt_datum=selected_date
    )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)
