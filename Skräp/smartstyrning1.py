
from flask import Flask, render_template, request, redirect, url_for
import json
import lgpio
from datetime import datetime
import atexit
from spotpris import fetch_elpriser
from yr_weather import get_weather_forecast

app = Flask(__name__)

# GPIO setup
RELAY_PIN = 17
h = lgpio.gpiochip_open(0)

def cleanup():
    lgpio.gpio_write(h, RELAY_PIN, 0)
    lgpio.gpiochip_close(h)

def safe_claim_output(handle, pin):
    try:
        lgpio.gpio_claim_output(handle, pin)
    except lgpio.error:
        print("GPIO busy, attempting to clean up and retry")
        cleanup()
        lgpio.gpio_claim_output(handle, pin)

safe_claim_output(h, RELAY_PIN)
atexit.register(cleanup)

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'on':
            lgpio.gpio_write(h, RELAY_PIN, 1)
        elif action == 'off':
            lgpio.gpio_write(h, RELAY_PIN, 0)
        return redirect(url_for('home'))

    prices = fetch_elpriser()
    weather = get_weather_forecast()
    billigaste = sorted(prices, key=lambda x: x['price'])[:6]
    billigaste_tider = [p['time'] for p in billigaste]
    return render_template('index.html', prices=prices, billigaste_tider=billigaste_tider, weather=weather)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
