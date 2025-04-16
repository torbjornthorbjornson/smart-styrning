from datetime import datetime, timedelta
import random
import pymysql

# Skapa testdata
now = datetime.now()
rows = []
for i in range(24):
    t = now - timedelta(hours=23 - i)
    level = random.randint(1500, 4000)
    pressure = round(random.uniform(2.0, 3.5), 2)
    p1 = round(random.uniform(30.0, 50.0), 1) if level < 3000 else round(random.uniform(10.0, 30.0), 1)
    p2 = round(random.uniform(0.0, 15.0), 1) if level < 2500 else 0.0
    p3 = 0.0
    rows.append((t.strftime("%Y-%m-%d %H:%M:%S"), level, pressure, p1, p2, p3))

# Anslut till databasen
conn = pymysql.connect(
    host="localhost",
    user="root",
    password="DITT_LÖSENORD",  # eller ta bort denna rad om du använder .my.cnf
    database="vattenstyrning"
)

with conn:
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM water_status")
        for row in rows:
            cursor.execute("""
                INSERT INTO water_status (timestamp, level_liters, system_pressure, pump1_freq, pump2_freq, pump3_freq)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, row)
    conn.commit()

print("✅ Simulerad vattendata inskriven!")
