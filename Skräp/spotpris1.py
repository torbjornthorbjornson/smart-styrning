import requests
from datetime import datetime, timedelta

def fetch_elpriser():
    today = datetime.now().strftime("%Y/%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y/%m-%d")

    url_tomorrow = f"https://www.elprisetjustnu.se/api/v1/prices/{tomorrow}_SE3.json"
    url_today = f"https://www.elprisetjustnu.se/api/v1/prices/{today}_SE3.json"

    try:
        print(f"Försöker hämta priser för imorgon från: {url_tomorrow}")
        response = requests.get(url_tomorrow)
        response.raise_for_status()
        data_tomorrow = response.json()
        print("Priser för imorgon hämtade framgångsrikt:", data_tomorrow)
        return data_tomorrow  # Om priserna för imorgon finns, returnera dem
    except requests.exceptions.RequestException as e:
        print("⚠️ Inga elpriser för imorgon tillgängliga, eller fel uppstod:", e)

    try:
        print(f"Försöker hämta priser för idag från: {url_today}")
        response = requests.get(url_today)
        response.raise_for_status()
        data_today = response.json()
        print("Dagens priser hämtade framgångsrikt:", data_today)
        return data_today  # Om morgondagens saknas, returnera dagens priser istället
    except requests.exceptions.RequestException as e:
        print("🚨 Fel vid hämtning av dagens elpriser:", e)
        return []

if __name__ == "__main__":
    prices = fetch_elpriser()
    print("Priser hämtade:", prices)
