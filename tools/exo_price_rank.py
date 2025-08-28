#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import configparser
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pymysql  # PyMySQL 1.1.x

TZ_DEFAULT = "Europe/Stockholm"

def read_mysql_creds_from_mycnf(path="~/.my.cnf", section="client"):
    cfg = configparser.ConfigParser()
    cfg.read(os.path.expanduser(path))
    if section not in cfg:
        raise RuntimeError(f"Hittar inte sektionen [{section}] i {path}")
    get = cfg[section].get
    host = get("host", "localhost")
    user = get("user")
    password = get("password")
    db = get("database", "smart_styrning")
    port = int(get("port", "3306"))
    if not user or not password:
        raise RuntimeError("Saknar user/password i ~/.my.cnf [client]")
    return dict(host=host, user=user, password=password, database=db, port=port)

def pick_target_day_local(now_utc, tz):
    local_now = now_utc.astimezone(tz)
    today_local = local_now.date()
    tomorrow_local = today_local + timedelta(days=1)
    yesterday_local = today_local - timedelta(days=1)
    return (tomorrow_local, today_local, yesterday_local)

def local_day_to_utc_range(local_day, tz):
    start_local = datetime(local_day.year, local_day.month, local_day.day, 0, 0, 0, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

def fetch_prices_utc(conn, table, price_col, start_utc, end_utc):
    q = f"""
        SELECT `datetime`, `{price_col}` AS price
        FROM `{table}`
        WHERE `datetime` >= %s AND `datetime` < %s
        ORDER BY `datetime` ASC
    """
    with conn.cursor() as cur:
        cur.execute(q, (start_utc, end_utc))
        rows = cur.fetchall()
    out = []
    for dt, p in rows:
        try:
            pf = float(p)
        except Exception:
            continue
        # MySQL ger naive dt → sätt UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        out.append((dt, pf))
    return out

def ensure_24_hours(local_day, tz, rows_utc):
    prices = [math.nan] * 24
    for dt_utc, price in rows_utc:
        dt_local = dt_utc.astimezone(tz)
        if dt_local.date() == local_day:
            prices[dt_local.hour] = price
    return prices

def compute_rank(prices):
    indexed = [(i, p) for i, p in enumerate(prices)]
    have = [(i, p) for (i, p) in indexed if not math.isnan(p)]
    miss = [i for (i, p) in indexed if math.isnan(p)]
    have_sorted = sorted(have, key=lambda t: (t[1], t[0]))
    rank = [99] * 24
    for r, (h, _) in enumerate(have_sorted):
        rank[h] = r
    for h in miss:
        rank[h] = 99
    return rank

def build_masks(prices, cheap_pct=-0.30, exp_pct=0.50):
    vals = [p for p in prices if not math.isnan(p)]
    if not vals:
        return {"EX": {"L": 0, "H": 0}, "EC": {"L": 0, "H": 0}, "median": math.nan, "cheap_pct": cheap_pct, "exp_pct": exp_pct}
    s = sorted(vals)
    n = len(s)
    median = s[n//2] if n % 2 == 1 else 0.5*(s[n//2 - 1] + s[n//2])

    EC_L = EC_H = EX_L = EX_H = 0
    ec_thr = median * (1.0 + cheap_pct)
    ex_thr = median * (1.0 + exp_pct)

    for h in range(24):
        p = prices[h]
        if math.isnan(p):
            continue
        if p <= ec_thr:
            (EC_L := EC_L | (1 << h)) if h < 16 else (EC_H := EC_H | (1 << (h - 16)))
        if p >= ex_thr:
            (EX_L := EX_L | (1 << h)) if h < 16 else (EX_H := EX_H | (1 << (h - 16)))

    return {
        "EX": {"L": EX_L, "H": EX_H},
        "EC": {"L": EC_L, "H": EC_H},
        "median": median,
        "cheap_pct": cheap_pct,
        "exp_pct": exp_pct,
    }

def main():
    ap = argparse.ArgumentParser(description="Skapa EXO/Arigo price_rank JSON för ett dygn.")
    ap.add_argument("--site-id", default=os.environ.get("SITE_ID","C1"))
    ap.add_argument("--tz", default=TZ_DEFAULT)
    ap.add_argument("--db", default=None)
    ap.add_argument("--table", default="electricity_prices")
    ap.add_argument("--price-column", default="price")
    ap.add_argument("--mycnf", default="~/.my.cnf")
    ap.add_argument("--out", default="-")
    ap.add_argument("--cheap-pct", type=float, default=-0.30)
    ap.add_argument("--exp-pct", type=float, default=0.50)
    args = ap.parse_args()

    tz = ZoneInfo(args.tz)
    now_utc = datetime.now(timezone.utc)

    creds = read_mysql_creds_from_mycnf(args.mycnf, "client")
    if args.db:
        creds["database"] = args.db

    candidates = pick_target_day_local(now_utc, tz)
    chosen_day = None
    chosen_prices = None

    conn = pymysql.connect(
        host=creds["host"], user=creds["user"], password=creds["password"],
        database=creds["database"], port=creds["port"], autocommit=True, cursorclass=pymysql.cursors.Cursor
    )
    try:
        for d in candidates:
            s_utc, e_utc = local_day_to_utc_range(d, tz)
            rows = fetch_prices_utc(conn, args.table, args.price_column, s_utc, e_utc)
            prices = ensure_24_hours(d, tz, rows)
            if all(not math.isnan(p) for p in prices):
                chosen_day, chosen_prices = d, prices
                break
        if chosen_day is None:
            best = None
            for d in candidates:
                s_utc, e_utc = local_day_to_utc_range(d, tz)
                rows = fetch_prices_utc(conn, args.table, args.price_column, s_utc, e_utc)
                prices = ensure_24_hours(d, tz, rows)
                count = sum(0 if math.isnan(p) else 1 for p in prices)
                if best is None or count > best[0]:
                    best = (count, d, prices)
            _, chosen_day, chosen_prices = best
    finally:
        conn.close()

    rank = compute_rank(chosen_prices)
    masks = build_masks(chosen_prices, cheap_pct=args.cheap_pct, exp_pct=args.exp_pct)
    price_stamp = int(chosen_day.strftime("%Y%m%d"))

    payload = {
        "site_id": args.site_id,
        "day": chosen_day.isoformat(),
        "tz": args.tz,
        "price_stamp": price_stamp,
        "price_rank": rank,
        "masks": {"EX": {"L": masks["EX"]["L"], "H": masks["EX"]["H"]},
                  "EC": {"L": masks["EC"]["L"], "H": masks["EC"]["H"]}},
        "meta": {
            "generated_at": datetime.now(tz).isoformat(timespec="seconds"),
            "median": masks.get("median"),
            "cheap_pct": args.cheap_pct,
            "exp_pct": args.exp_pct,
        },
    }

    out_str = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.out in ("-", "/dev/stdout"):
        print(out_str)
    else:
        out_path = os.path.abspath(os.path.expanduser(args.out))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out_str)
        print(f"Wrote {out_path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
