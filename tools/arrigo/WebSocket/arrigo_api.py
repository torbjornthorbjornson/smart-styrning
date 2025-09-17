import requests

# ==== KONFIG ====
LOGIN_URL = "https://arrigo.svenskastenhus.se/arrigo/api/login"  # Rätt URL för inloggning
USER = 'APIUser'
PASS = 'API_S#are'

def login():
    """Logga in på Arrigo API och hämta Auth Token."""
    response = requests.post(LOGIN_URL, json={"username": USER, "password": PASS})
    response.raise_for_status()  # Kontrollera om anropet lyckades
    return response.json()["authToken"]

if __name__ == "__main__":
    # Testa inloggning
    token = login()
    print(f"Auth Token: {token}")