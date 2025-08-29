#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Genererar EXO/Arrigo-dagspaket med:
- price_rank[24] där index = lokal timme 0..23 (Europe/Stockholm) och värde = rank (0 = billigast)
- EX/EC-masker baserade på median
- metadata inkl. day (YYYY-MM-DD), tz, price_stamp

Strategi:
- Priser i DB antas vara lagrade som UTC-naiva DATETIME (från spotpris.py).
- Dygn väljs i lokal svensk tid (imorgon -> idag -> igår).
- Vi bygger [start_utc, end_utc) för lokalen och hämtar rader i det fönstret.
- Varje rad mappas till lokal timme och fyller en 24-längdslista (NaN om saknas).
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json
from datetime import datetime, date, time, timedelta
import pytz, pymysql

STHLM = pytz.timezone("Europe/Stockholm")
UTC    = pytz.UTC

def db():
    return pymysql.connect(
        read_default_file="/home/runerova/.my.cnf",
        database="smart_styrning",
        cursorclass=pymysql.cursors.DictCursor
    )

def local_day_to_utc_window(local_day: date, tzname: str):
    tz = pytz.timezone(tzname)
    local_midnight = tz.localize(datetime.combine(local_day, time(0,0)))
    start_utc = local_midnight.astimezone(UTC).replace(tzinfo=None)
    end_utc   = (local_midnight + timedelta(days=1)).astimezone(UTC).replace(tzinfo=None)
    return start_utc, end_utc

def pack_mask(hours):
    """hours = set({int hour_indexes}) -> (L, H) 24-bit"""
    bits = 0
    for h in hours:
        if 0 <= h <= 23:
            bits |= (1 << h)
    L = bits & 0xFFFF              # bits 0..15
    H = (bits >> 16) & 0xFFFF      # bits 16..31 (vi använder 16..23)
    return L, H

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--site-id", required=True)
    p.add_argument("--day", help="YYYY-MM-DD (svensk dag). Default: idag i vald tz")
    p.add_argument("--tz", default="Europe/Stockholm")
    p.add_argument("--cheap-pct", type=float, default=-0.30,
                   help="extremt billigt = pris <= median * (1 + cheap_pct)")
    p.add_argument("--exp-pct", type=float, default=0.50,
                   help="extremt dyrt    = pris >= median * (1 + exp_pct)")
    p.add_argument("--out", default="-", help="- = stdout, annars fil")
    p.add_argument("--persist", action="store_true", help="skriv in i MariaDB-tabellen exo_day_rank")
    args = p.parse_args()

    # vald svensk dag
    if args.day:
        local_day = datetime.strptime(args.day, "%Y-%m-%d").date()
    else:
        local_day = datetime.now(STHLM).date()

    utc_start, utc_end = local_day_to_utc_window(local_day, args.tz)

    # hämta dygnets priser (UTC i DB)
    with db() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT datetime, price
            FROM electricity_prices
            WHERE datetime >= %s AND datetime < %s
            ORDER BY datetime
        """, (utc_start, utc_end))
        rows = cur.fetchall()

    if len(rows) != 24:
        raise SystemExit(f"Förväntade 24 timpriser, fick {len(rows)}. Kontrollera inläsningen.")

    # mappa till [ (hour_index, price) ... ] i svensk tid
    hour_price = []
    for r in rows:
        hour_local = UTC.localize(r["datetime"]).astimezone(STHLM).hour
        hour_price.append((hour_local, float(r["price"])))

    # sortera per pris -> prisstege: index = rank (0 billigast) -> värde = timindex
    price_rank = [h for (h, _) in sorted(hour_price, key=lambda t: t[1])]

    # median + masker
    prices_sorted = sorted([p for (_, p) in hour_price])
    median = (prices_sorted[11] + prices_sorted[12]) / 2.0  # 24 värden

    cheap_thr = median * (1.0 + args.cheap_pct)  # cheap_pct är negativ
    exp_thr   = median * (1.0 + args.exp_pct)

    cheap_hours = {h for (h, p) in hour_price if p <= cheap_thr}
    exp_hours   = {h for (h, p) in hour_price if p >= exp_thr}

    ecL, ecH = pack_mask(cheap_hours)
    exL, exH = pack_mask(exp_hours)

    payload = {
        "site_id": args.site_id,
        "day": local_day.strftime("%Y-%m-%d"),
        "tz": args.tz,
        "price_stamp": int(local_day.strftime("%Y%m%d")),
        "price_rank": price_rank,          # element i = rank; värde = timindex 0..23
        "masks": {
            "EX": {"L": exL, "H": exH},
            "EC": {"L": ecL, "H": ecH},
        },
        "meta": {
            "generated_at": datetime.now(STHLM).isoformat(timespec="seconds"),
            "median": median,
            "cheap_pct": args.cheap_pct,
            "exp_pct": args.exp_pct,
        },
    }

    if args.persist:
        with db() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO exo_day_rank
                    (site_id, day, tz, price_stamp, price_rank,
                     ex_mask_L, ex_mask_H, ec_mask_L, ec_mask_H,
                     median, cheap_pct, exp_pct, generated_at)
                VALUES (%s,%s,%s,%s, %s, %s,%s,%s,%s, %s,%s,%s, %s)
                ON DUPLICATE KEY UPDATE
                    tz=VALUES(tz),
                    price_stamp=VALUES(price_stamp),
                    price_rank=VALUES(price_rank),
                    ex_mask_L=VALUES(ex_mask_L),
                    ex_mask_H=VALUES(ex_mask_H),
                    ec_mask_L=VALUES(ec_mask_L),
                    ec_mask_H=VALUES(ec_mask_H),
                    median=VALUES(median),
                    cheap_pct=VALUES(cheap_pct),
                    exp_pct=VALUES(exp_pct),
                    generated_at=VALUES(generated_at)
            """, (
                args.site_id, local_day, args.tz, int(local_day.strftime("%Y%m%d")),
                json.dumps(price_rank), exL, exH, ecL, ecH,
                median, args.cheap_pct, args.exp_pct, datetime.utcnow()
            ))
            conn.commit()

    if args.out == "-" or not args.out:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
