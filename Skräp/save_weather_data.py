import sqlite3

def save_to_database(data):
    conn = sqlite3.connect('/home/runerova/weather_data.db')  # Specifiera fullständig sökväg för tydlighet
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS weather (timestamp TEXT, temperature REAL)''')
    for time, temp in data.items():
        c.execute('''INSERT INTO weather VALUES (?,?)''', (time, temp))
    conn.commit()
    conn.close()

# Exempeldata för att testa funktionen
example_data = {
    '2021-01-01T00:00:00Z': 22.5,
    '2021-01-01T01:00:00Z': 21.9
}

save_to_database(example_data)
