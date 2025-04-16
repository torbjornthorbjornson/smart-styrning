from datetime import datetime, timedelta
import random
import pymysql

# Anslut till databasen
conn = pymysql.connect(
    host="localhost",
    user="smartuser",
    password="5675",
    database="vattenstyrning"
)

cursor = conn.cursor()

# Skapa testdata för 24 timmar bakåt
now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
data = []
for i in range(24):
    ts = now - timedelta(hours=23 - i)
    level = random.randint(1500, 4000)  # liter i bassängen
    pressure = round(random.uniform(1.5, 5.0), 2)  # bar
    freq1 = round(random.uniform(20, 80), 1)       # pump 1
    freq2 = round(random.uniform(0, 50), 1)        # pump 2
    freq3 = round(random.uniform(0, 30), 1)        # pump 3
    data.append((ts, level, pressure, freq1, freq2, freq3))

# Spara till databasen
cursor.executemany(
    "INSERT INTO water_status (timestamp, level_liters, system_pressure, pump1_freq, pump2_freq, pump3_freq) VALUES (%s, %s, %s, %s, %s, %s)",
    data
)

conn.commit()
cursor.close()
conn.close()

print("✅ Fejkdata infört i databasen vattenstyrning!")

