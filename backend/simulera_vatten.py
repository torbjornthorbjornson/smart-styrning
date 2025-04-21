from datetime import datetime, timedelta
import random
import pymysql
import configparser

# Läs databasuppgifter från .my.cnf
config = configparser.ConfigParser()
config.read("/home/runerova/.my.cnf")
user = config["client"]["user"]
password = config["client"]["password"]

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
    booster = round(random.uniform(35.0, 60.0), 1) if pressure < 3.0 else round(random.uniform(20.0, 35.0), 1)
    
    rows.append((t.strftime("%Y-%m-%d %H:%M:%S"), level, pressure, p1, p2, p3, booster))

# Anslut till databasen med smartuser
conn = pymysql.connect(
    host="localhost",
    user=user,
    password=password,
    database="smart_styrning"
)

with conn:
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM water_status")
        for row in rows:
            cursor.execute("""
                INSERT INTO water_status (timestamp, level_liters, system_pressure, pump1_freq, pump2_freq, pump3_freq, booster_freq)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, row)
    conn.commit()

print("✅ Simulerad vattendata inskriven till smart_styrning!")