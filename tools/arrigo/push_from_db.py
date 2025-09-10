#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_from_db.py (tolerant variant, array-only)
- Hämtar elpriser från DB
- Bygger rank-array (0..23)
- Fyller ut saknade timmar med rank 23 (sämst)
- Pushar alltid komplett array till Arrigo
"""

import os, sys, json, datetime as dt
from zoneinfo import ZoneInfo
import pymysql
import requests
from configparser import ConfigParser

TZ = ZoneInfo("Europe/Stockholm")
LOG_PATH = "/home/runerova/smartweb/tools/arrigo/logs/arrigo_push.log"

def log(msg):
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a") as f:
        f.write(f"{now} {msg}\n")
    print(msg)

def read_db_creds():
    cp = ConfigParser()
    cp.read("/home/runerova/.my.cnf")
    return dict(
        host=cp.get("client", "host", fallback="localhost"),
        user=cp.get("client", "user"),
        password=cp.get("client", "password"),
        database=cp.get("client", "database", fallback="smart_styrning")
    )

def sql_connect():
    creds = read_db_creds()
    return pymysql.connect(
        host=creds["host"], user=creds["user"], password=creds["password"],
        database=creds["database"], cursorclass=pymysql.cursors.DictCursor
    )

def local_day_window(which):
    today_local = dt.datetime.now(TZ).date()
    if which == "today":
        day = today_local
    elif which == "tomorrow":
        day = today_local + dt.timedelta(days=1)
    else:
        raise ValueError("Använd: today | tomorrow")
    start = dt.datetime.combine(day, dt.time(0,0), TZ)
    end   = start + dt.timedelta(days=1)
    return start.astimezone(dt.timezone.utc), end.astimezone(dt.timezone.utc)

def fetch_prices(start_utc, end_utc):
    sql = """
    SELECT datetime, price
    FROM electricity_prices
    WHERE datetime >= %s AND datetime < %s
    ORDER BY datetime ASC
    """
    with sql_connect() as conn, conn.cursor() as cur:
        cur.execute(sql, (start_utc, end_utc))
        return cur.fetchall()

def build_rank(rows, day_local):
    prices = [None]*24
    for r in rows:
        t_local = r["datetime"].replace(tzinfo=dt.timezone.utc).astimezone(TZ)
        prices[t_local.hour] = float(r["price"])
    # ranka
    values = [p if p is not None else float("inf") for p in prices]
    order = sorted(range(24), key=lambda i: (values[i], i))
    rank = [None]*24
    for r, idx in enumerate(order):
        rank[idx] = r
    # saknade timmar
    missing = [i for i, p in enumerate(prices) if p is None]
    if missing:
        log(f"⚠️ Saknade timmar {missing} för {day_local}, fyllde rank 23.")
        for i in missing:
            rank[i] = 23
    return rank

def arrigo_login(session, login_url, user, passwd, verify):
    r = session.post(login_url, json={"username": user, "password": passwd}, timeout=20, verify=verify)
    r.raise_for_status()
    return r.json().get("authToken")

def arrigo_push(session, graphql_url, pvl_b64, rank, verify):
    writes = [{"key": f"{pvl_b64}:{i}", "value": int(rank[i])} for i in range(24)]
    mutation = """
    mutation ($variables:[VariableKeyValue!]!){
      writeData(variables:$variables)
    }
    """
    payload = {"query": mutation, "variables": {"variables": writes}}
    r = session.post(graphql_url, json=payload, timeout=30, verify=verify)
    r.raise_for_status()
    data = r.json()
    log("GraphQL svar: " + json.dumps(data)[:400])
    return data

def main():
    which = os.environ.get("RANK_WHEN", "today")
    login_url   = os.environ.get("ARRIGO_LOGIN_URL")
    graphql_url = os.environ.get("ARRIGO_GRAPHQL_URL")
    user        = os.environ.get("ARRIGO_USER")
    passwd      = os.environ.get("ARRIGO_PASS")
    pvl_b64     = os.environ.get("PVL_B64") or os.environ.get("ARRIGO_PVL_PATH")
    insecure    = os.environ.get("ARRIGO_INSECURE", "0") == "1"

    if not all([login_url, graphql_url, user, passwd, pvl_b64]):
        log("❌ Saknar miljövariabler. Avbryter.")
        sys.exit(1)

    start_utc, end_utc = local_day_window(which)
    rows = fetch_prices(start_utc, end_utc)
    day_local = start_utc.astimezone(TZ).date()
    log(f"Hämtade {len(rows)} rader för {which} ({day_local})")

    rank = build_rank(rows, day_local)

    sess = requests.Session()
    verify = not insecure
    token = arrigo_login(sess, login_url, user, passwd, verify)
    sess.headers.update({"Authorization": f"Bearer {token}"})
    arrigo_push(sess, graphql_url, pvl_b64, rank, verify)
    log(f"✅ Push klar för {which} ({day_local})")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ FEL: {e}")
        sys.exit(1)
