from flask import Flask, render_template, request, redirect, url_for
from gpiozero import LED
import atexit
from spotpris import fetch_elpriser
from yr_weather import get_weather_forecast

app = Flask(__name__)

# GPIO setup
relay = LED(17)  # Använd gpiozero för att hantera RELAY_PIN

def cleanup():
    relay.off()

atexit.register(cleanup)  # Rengör GPIO-pinnar vid avslutning

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'on':
            relay.on()
        elif action == 'off':
            relay.off()
        return redirect(url_for('home'))

    prices = fetch_elpriser()
    weather = get_weather_forecast()
    try:
        billigaste = sorted(prices, key=lambda x: x.get('price', float('inf')))[:6]
        billigaste_tider = [p.get('time', 'Unknown time') for p in billigaste]  # Korrekt stängd parentes
    except Exception as e:
        print(f"Error processing price data: {e}")
        billigaste_tider = []

    return render_template('index.html', prices=prices, billigaste_tider=billigaste_tider, weather=weather)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)  # Använd port 5001 för att undvika konflikter
