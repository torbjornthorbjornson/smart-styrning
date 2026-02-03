#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, json
from datetime import datetime
from zoneinfo import ZoneInfo
import pymysql, requests
from configparser import ConfigParser

TZ  = ZoneInfo("Europe/Stockholm")
UTC = ZoneInfo("UTC")

def read_db_config():
    cfg = ConfigParser()
    cfg.read("/home/runerova/.my.cnf")
    return {
        "host": "localhost",
        "user": cfg["client"]["user"],
        "password": cfg["client"]["password"],
        "database": "smart_styrning",
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }

def build_verify():
    if os.getenv("ARRIGO_INSECURE", "0") == "1":
        return False
    return os.getenv("REQUESTS_CA_BUNDLE") or True

def arrigo_login():
    login_url = os.getenv("ARRIGO_LOGIN_URL")
    user      = os.getenv("ARRIGO_USER") or os.getenv("ARRIGO_USERNAME")
    password  = os.getenv("ARRIGO_PASS") or os.getenv("ARRIGO_PASSWORD")
    verify    = build_verify()

    if not login_url or not user or not password:
        raise SystemExit("Saknar ARRIGO_LOGIN_URL / ARRIGO_USER / ARRIGO_PASS")

    r = requests.post(login_url, json={"username": user, "password": password},
                      timeout=15, verify=verify)
    r.raise_for_status()
    tok = r.json().get("authToken")
    if not tok:
        raise SystemExit("Inget authToken i login-svar")
    return tok

def gql(token, query, variables):
    url    = os.getenv("ARRIGO_GRAPHQL_URL")
    verify = build_verify()
    if not url:
        raise SystemExit("Saknar ARRIGO_GRAPHQL_URL")

    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "variables": variables},
        timeout=30,
        verify=verify
    )
    r.raise_for_status()
    j = r.json()
    if "errors" in j:
        raise SystemExit("GraphQL-fel: " + str(j["errors"]))
    return j["data"]

def read_vars_from_pvl(token, pvl_path):
    q = """
    query($path:String!){
      data(path:$path){
        variables { technicalAddress value }
      }
    }
    """
    data = gql(token, q, {"path": pvl_path})
    vars_list = (data.get("data") or {}).get("variables") or []
    return {v["technicalAddress"]: v.get("value") for v in vars_list if v.get("technicalAddress")}

def extract_heat_plan_96(vals, prefix="Huvudcentral_C1.HEAT_PLAN"):
    out = [0] * 96
    for k, v in vals.items():
        if not k.startswith(prefix):
            continue

        idx = None

        # Format A: Huvudcentral_C1.HEAT_PLAN(5)
        m = re.search(r"\((\d{1,2})\)\s*$", k)
        if m:
            idx = int(m.group(1))

        # Format B: Huvudcentral_C1.HEAT_PLAN_05_00:00 (om det finns)
        if idx is None:
            tail = k[len(prefix):]
            m = re.search(r"_(\d{2})_", tail)
            if m:
                idx = int(m.group(1))

        if idx is None or not (0 <= idx < 96):
            continue

        try:
            out[idx] = int(float(v)) if v is not None else 0
        except Exception:
            out[idx] = 0

    return out


def upsert_plan(site_code, plan_type, day_local, periods):
    fetched_at = datetime.now(UTC).replace(tzinfo=None)  # UTC-naiv
    conn = pymysql.connect(**read_db_config())
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE() AS db")
            print("DB:", cur.fetchone()["db"])

            cur.execute("""
                INSERT INTO arrigo_plan_cache (site_code, plan_type, day_local, fetched_at, periods)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  fetched_at = VALUES(fetched_at),
                  periods    = VALUES(periods)
            """, (site_code, plan_type, day_local, fetched_at, json.dumps(periods)))

        conn.commit()
    finally:
        conn.close()

    print(f"✅ Sparade {plan_type} för {site_code} {day_local} (1:or={sum(periods)})")


def main():
    site_code = os.getenv("SITE_CODE", "HALTORP244")
    plan_type = "HEAT_PLAN"

    # Svensk dag (idag)
    day_local = datetime.now(TZ).date()

    pvl_path = os.getenv("ARRIGO_PVL_B64") or os.getenv("ARRIGO_PVL_PATH")
    if not pvl_path:
        raise SystemExit("Saknar ARRIGO_PVL_B64 / ARRIGO_PVL_PATH")

    token = arrigo_login()
    vals  = read_vars_from_pvl(token, pvl_path)

    heat = extract_heat_plan_96(vals, prefix="Huvudcentral_C1.HEAT_PLAN")

    upsert_plan(site_code, plan_type, day_local, heat)

if __name__ == "__main__":
    main()
