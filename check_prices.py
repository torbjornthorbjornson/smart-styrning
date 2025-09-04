#!/usr/bin/env python3
import pymysql

conn = pymysql.connect(read_default_file="/home/runerova/.my.cnf",
                       database="smart_styrning",
                       cursorclass=pymysql.cursors.DictCursor)

with conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DATE(CONVERT_TZ(datetime,'UTC','Europe/Stockholm')) AS svensk_dag,
                   COUNT(*) AS timmar
            FROM electricity_prices
            GROUP BY svensk_dag
            HAVING COUNT(*) NOT IN (23,24,25)
            ORDER BY svensk_dag DESC
        """)
        rows = cur.fetchall()

if not rows:
    print("✅ Alla dagar har rätt antal timmar (23/24/25).")
else:
    print("⚠️ Följande dagar har fel antal timmar:")
    for r in rows:
        print(f"  {r['svensk_dag']}: {r['timmar']} timmar")
  database="smart_styrning",
                       cursorclass=pymysql.cursors.DictCursor)

  msg = "⚠️ Följande dagar har fel antal timmar:"
    print(msg)
    logging.warning(msg)
    for r in rows:
        line = f"  {r['svensk_dag']}: {r['timmar']} timmar"
        print(line)
        logging.warning(line)
read_default_file="/home/runerova/.my.cnf",
                       database="smart_styrning",
                       cursorclass=pymysql.cursors.DictCursor)

with conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DATE(CONVERT_TZ(datetime,'UTC','Europe/Stockholm')) AS svensk_dag,
                   COUNT(*) AS timmar
            FROM electricity_prices
            GROUP BY svensk_dag
            HAVING COUNT(*) NOT IN (23,24,25)
            ORDER BY svensk_dag DESC
        """)
        rows = cur.fetchall()

if not rows:
    print("✅ Alla dagar har rätt antal timmar (23/24/25).")
else:
    print("⚠️ Följande dagar har fel antal timmar:")
    for r in rows:
        print(f"  {r['svensk_dag']}: {r['timmar']} timmar")
