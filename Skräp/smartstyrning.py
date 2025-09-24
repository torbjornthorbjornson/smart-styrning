from flask import Flask, render_template
import matplotlib.pyplot as plt
from io import BytesIO
import base64

app = Flask(__name__)

def plot_prices(prices):
    hours = [p['time'][:2] for p in prices if isinstance(p, dict) and 'time' in p and 'price' in p]
    values = [p['price'] for p in prices if isinstance(p, dict) and 'time' in p and 'price' in p]
    colors = ['green' if value == min(values) else 'blue' for value in values]

    plt.figure(figsize=(10, 5))
    plt.bar(hours, values, color=colors)
    plt.xlabel('Time')
    plt.ylabel('Price (SEK/kWh)')
    plt.title('Electricity Prices for Next 24 Hours')
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    return image_base64

@app.route('/')
def home():
    prices = fetch_elpriser()  # Antag att detta returnerar riktig prisdata
    image = plot_prices(prices)
    return render_template('index.html', image=image)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
