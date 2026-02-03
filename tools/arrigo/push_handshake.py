#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_handshake.py
- Läser EXOL-handshake via Arrigo GraphQL
- Skickar dagens eller morgondagens 96 perioder enligt PI_PUSH_DAY
- Hanterar TD_READY / TM_READY och väntar om morgondagens priser saknas
- PI sätter endast ACK=1, EXOL nollar det själv
"""

import os, time, requests, pymysql
from datetime import date, timedelta
from configparser import ConfigParser
from push_from_db import (
    fetch_prices,
    build_rank_and_masks,
    daily_avg_oat,
    build_verify,
    ensure_b64,
    gql,
    arrigo_login,
)

# === Grundinställningar ===
LOGIN_URL   = os.getenv("ARRIGO_LOGIN_URL")
GRAPHQL_URL = os.getenv("ARRIGO_GRAPHQL_URL")
USER        = os.getenv("ARRIGO_USER")
PASS        = os.getenv("ARRIGO_PASS")
PVL_RAW     = os.getenv("ARRIGO_PVL_B64") or os.getenv("ARRIGO_PVL_PATH")
PVL_B64     = ensure_b64(PVL_RAW)
VERIFY      = build_verify()

# === Hjälpfunktioner ===
def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)

def read_vars(token):
    q = """
    query($path:String!){
      data(path:$path){
        variables { technicalAddress value }
      }
    }
    """
    data = gql(GRAPHQL_URL, token, q, {"path": PVL_B64}, VERIFY)
    vars_list = (data.get("data") or {}).get("variables") or []
    vals = {v["technicalAddress"]: v["value"] for v in vars_list if "value" in v}
    return vals

def write_var(token, tech_addr, val):
    """Skriv värde till exakt technicalAddress."""
    m = "mutation($v:[VariableKeyValue!]!){writeData(variables:$v)}"
    gql(GRAPHQL_URL, token, m, {"v":[{"key":f"{PVL_B64}:{tech_addr}","value":str(val)}]}, VERIFY)

# === Huvudloop ===
def main():
    token = arrigo_login(LOGIN_URL, USER, PASS, VERIFY)
    log("🔌 Startar handshake-loop mot Arrigo")

    while True:
        try:
            vals = read_vars(token)
        except HTTPError as e:
            code = getattr(getattr(e, 'response', None), 'status_code', None)
            if code == 401:
                log('🔑 401 på read_vars – loggar in igen')
                token = login()
                time.sleep(2)
                continue
            raise


        req = int(vals.get("Huvudcentral_C1.PI_PUSH_REQ", 0))
        ack = int(vals.get("Huvudcentral_C1.PI_PUSH_ACK", 0))
        day = int(vals.get("Huvudcentral_C1.PI_PUSH_DAY", 0))
        td_ready = int(vals.get("Huvudcentral_C1.TD_READY", 0))
        tm_ready = int(vals.get("Huvudcentral_C1.TM_READY", 0))

        log(f"📅 Loopstatus: REQ={req}, ACK={ack}, DAY={day}, TD_READY={td_ready}, TM_READY={tm_ready}")

        if req == 1 and ack == 0:
            which = "today" if day == 0 else "tomorrow"

            # 🔍 Fallback: skicka inte morgondagen om den redan finns
            if which == "tomorrow" and tm_ready == 1:
                log("✅ Morgondagens priser redan laddade i EXOL – hoppar över push.")
                time.sleep(30)
                continue

            # 🔍 Fallback: skicka inte dagens om den redan är klar
            if which == "today" and td_ready == 1:
                log("✅ Dagens priser redan laddade i EXOL – hoppar över push.")
                time.sleep(30)
                continue

            # 📊 Läs ut rätt data från databasen
            rows, day_local = fetch_prices(which)
            if which == "tomorrow" and len(rows) < 90:
                log("⚠️ Morgondagens priser saknas i databasen – väntar med push.")
                time.sleep(60)
                continue

            log(f"📤 Push begärd ({which}) – skickar {len(rows)} perioder till Arrigo.")
            rank, ec, ex, slot_price = build_rank_and_masks(rows)
            today = date.today()
            oat_yday = daily_avg_oat(today - timedelta(days=1))
            oat_tmr  = daily_avg_oat(today + timedelta(days=1))

            from push_from_db import push_to_arrigo
            push_to_arrigo(rank, ec, ex, day_local, oat_yday, oat_tmr, slot_price)

            # ✅ Pi sätter endast ACK=1 – EXOL nollar själv
            for k in vals:
                if k.endswith(".PI_PUSH_ACK"):
                    write_var(token, k, 1)
                    log("✅ PI_PUSH_ACK satt till 1 (klar med överföring).")
                    break

        elif req == 0 and ack == 1:
            log("⏳ Väntar på att EXOL nollar ACK (Pi gör inget).")

        time.sleep(30)

# === Start ===
if __name__ == "__main__":
    main()
