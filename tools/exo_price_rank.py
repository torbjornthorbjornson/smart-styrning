#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EXO/Arrigo push – färdig att köra på din Raspberry Pi.

Vad skriptet gör:
1) Hämtar dygnets elpriser från MariaDB (UTC i DB, svensk logik).
2) Bygger:
   - price_rank[24]  (värde = timindex 0..23, där index = rank 0..23; 0 = billigast)
   - EC/EX-masker (24-bit, split L/H à 16 bit)
   - price_stamp = YYYYMMDD (skrivs till H i EXO)
3) Loggar in mot Arrigo /login → authToken
4) POST:ar en GraphQL-mutation till /graphql: Price_OK=0 → alla värden → Price_OK=1
5) (Valfritt) Läser tillbaka PVL för snabb verifikation

Körning (exempel):
  pip3 install requests pytz PyMySQL
  python3 exo_price_rank.py --site-id C1 --push --verify

Flaggor för att sätta Arrigo-uppgifter vid körning:
  --arrigo-base-url "https://din.host/arrigo/api"
  --arrigo-user api_pusher
  --arrigo-pass 'hemligt'
  --pvl-path "QVBJZGVtby5BcmVhRm9sZGVyVmlldy5GaWxlLkFQSVZhcmlibGVMaXN0LkZpbGU="

Du kan också använda env-variabler:
  export ARRIGO_BASE_URL="https://din.host/arrigo/api"
  export ARRIGO_USER="api_pusher"
  export ARRIGO_PASS="hemligt"
  export ARRIGO_PVL_PATH="QVBJZGVtby5BcmVhRm9sZGVyVmlldy5GaWxlLkFQSVZhcmlibGVMaXN0LkZpbGU="
"""

import argparse, json, os
from datetime import datetime, date, time, timedelta
from typing import Dict, Any, Iterable, List, Tuple

import pytz, pymysql, requests

# ======== TIDSZONER ========
STHLM = pytz.timezone("Europe/Stockholm")
UTC   = pytz.UTC


# ======== KONFIG – FYLL I DINA VÄRDEN (kan överskuggas av flaggor/env) ========
# Publik adress inkl. port (om ni har 80/443 duger hosten)
DEFAULT_ARRIGO_BASE_URL = os.getenv("ARRIGO_BASE_URL", "http://<DIN-PUBLIKA-ADRESS>/arrigo/api")  # <-- BYT!
DEFAULT_ARRIGO_USER     = os.getenv("ARRIGO_USER",     "api_pusher")                               # <-- BYT!
DEFAULT_ARRIGO_PASS     = os.getenv("ARRIGO_PASS",     "hemligt")                                   # <-- BYT!
DEFAULT_PVL_PATH        = os.getenv("ARRIGO_PVL_PATH", "QVBJZGVtby5BcmVhRm9zZGVyVmlldy5GaWxlLkFQSVZhcmlibGVMaXN0LkZpbGU=")  # <-- BYT!

# PVL-indexordning (matchar ditt projekt):
IDX_RANK_START = 0    # :0..:23
IDX_EC_L       = 24   # :24
IDX_EC_H       = 25   # :25
IDX_EX_L       = 26   # :26
IDX_EX_H       = 27   # :27
IDX_STAMP      = 28   # :28 (H)
IDX_OK         = 29   # :29 (L)


# ======== DB-anslutning (din .my.cnf används för auth) ========
def db():
    return pymysql.connect(
        read_default_file="/home/runerova/.my.cnf",      # <-- justera vid behov
        database="smart_styrning",
        cursorclass=pymysql.cursors.DictCursor
    )


# ======== Hjälpare ========
def local_day_to_utc_window(local_day: date, tzname: str) -> Tuple[datetime, datetime]:
    tz = pytz.timezone(tzname)
    local_midnight = tz.localize(datetime.combine(local_day, time(0,0)))
    start_utc = local_midnight.astimezone(UTC).replace(tzinfo=None)
    end_utc   = (local_midnight + timedelta(days=1)).astimezone(UTC).replace(tzinfo=None)
    return start_utc, end_utc


def pack_mask(hours: Iterable[int]) -> Tuple[int, int]:
    """hours = uppsättning timindex 0..23 → (L, H) som två 16-bit heltal."""
    bits = 0
    for h in hours:
        if 0 <= h <= 23:
            bits |= (1 << h)
    L = bits & 0xFFFF
    H = (bits >> 16) & 0xFFFF
    return L, H


def normalize_to_24_hours(rows: List[Dict[str, Any]]) -> List[Tuple[int, float]]:
    """
    Tar DB-rader (UTC-naiva datetime + price), mappar till svensk timme,
    och hanterar 23/25-timmarsdygn:
      - Om 25 timmar: medelvärde för den dubbla timmen (två rader samma timme).
      - Om 23 timmar: fyller den saknade timmen med grannmedel (eller närmast kända).
    Returnerar lista [(hour_local, price_float)] med exakt 24 unika timmar 0..23.
    """
    per_hour = {h: [] for h in range(24)}
    for r in rows:
        dt_utc = UTC.localize(r["datetime"])
        h_loc  = dt_utc.astimezone(STHLM).hour
        per_hour[h_loc].append(float(r["price"]))

    out = []
    # skapa en lista över tillgängliga timmar
    known_hours = [h for h,v in per_hour.items() if v]
    if not known_hours:
        raise SystemExit("Inga priser hittades i intervallet – kontrollera DB/filtrering.")

    for h in range(24):
        vals = per_hour[h]
        if len(vals) == 0:
            # fyll saknad timme – ta närmaste kända timmar runt h
            # hitta närmaste vänster/höger med värden
            left = h-1
            while left >= 0 and not per_hour[left]:
                left -= 1
            right = h+1
            while right <= 23 and not per_hour[right]:
                right += 1

            if left >= 0 and right <= 23 and per_hour[left] and per_hour[right]:
                price = (sum(per_hour[left])/len(per_hour[left]) + sum(per_hour[right])/len(per_hour[right])) / 2.0
            else:
                # fallback: använd närmast kända (vänster först, annars första kända)
                if left >= 0 and per_hour[left]:
                    price = sum(per_hour[left])/len(per_hour[left])
                else:
                    first = min(known_hours)
                    price = sum(per_hour[first])/len(per_hour[first])
        else:
            # normal eller dubbeltimme: medelvärde
            price = sum(vals)/len(vals)

        out.append((h, float(price)))

    return out


# ======== Bygg payload från DB ========
def build_payload_from_db(site_id: str, local_day: date, tzname: str,
                          cheap_pct: float, exp_pct: float) -> Dict[str, Any]:
    start_utc, end_utc = local_day_to_utc_window(local_day, tzname)

    with db() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT datetime, price
            FROM electricity_prices
            WHERE datetime >= %s AND datetime < %s
            ORDER BY datetime
        """, (start_utc, end_utc))
        rows = cur.fetchall()

    # Normalisera till exakt 24 timmarspriser i svensk tid (fixar 23/25h-dygn)
    hour_price = normalize_to_24_hours(rows)  # [(hour, price), ...]

    # Prisstege: index = rank (0..23), värde = timindex 0..23
    price_rank = [h for (h, _) in sorted(hour_price, key=lambda t: t[1])]

    # Median + trösklar
    sorted_prices = sorted([p for (_, p) in hour_price])
    median = (sorted_prices[11] + sorted_prices[12]) / 2.0

    cheap_thr = median * (1.0 + cheap_pct)  # cheap_pct är negativ
    exp_thr   = median * (1.0 + exp_pct)

    cheap_hours = {h for (h, p) in hour_price if p <= cheap_thr}
    exp_hours   = {h for (h, p) in hour_price if p >= exp_thr}

    ecL, ecH = pack_mask(cheap_hours)
    exL, exH = pack_mask(exp_hours)

    payload = {
        "site_id": site_id,
        "day": local_day.strftime
