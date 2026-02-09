#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""readback_heatplan_to_db.py  (WORKER / LIBRARY)

ANSVAR:
- Läser HEAT_PLAN(0..95) från Arrigo via redan inloggad token (injectad från orchestrator)
- Sparar plan i MariaDB table arrigo_plan_cache

VIKTIGT:
- Loggar ALDRIG in mot Arrigo när modulen används som worker
- Kan köras standalone för felsökning (då används orchestratorns login)
"""

import json
import os
import re
from datetime import datetime

import _bootstrap  # noqa: F401

from smartweb_backend.db.connection import get_connection
from smartweb_backend.time_utils import today_local_date, utc_now_naive

Q_READ_VARS = "query($p:String!){ data(path:$p){ variables{ technicalAddress value } } }"


def read_vars_from_pvl(gql_fn, token: str, pvl_b64: str):
    """Returnerar dict TA->value för alla variabler i PVL."""
    data = gql_fn(token, Q_READ_VARS, {"p": pvl_b64})
    vars_list = (data.get("data") or {}).get("variables") or []
    return {
        v["technicalAddress"]: v.get("value")
        for v in vars_list
        if v.get("technicalAddress")
    }

def extract_heat_plan_96(vals, prefix: str):
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


def read_heat_plan_96(gql_fn, token: str, pvl_b64: str, prefix: str) -> list[int]:
    """Läser HEAT-planen (96 perioder) från Arrigo och returnerar list[int]."""
    vals = read_vars_from_pvl(gql_fn, token, pvl_b64)
    return extract_heat_plan_96(vals, prefix=prefix)


def upsert_plan(site_code, plan_type, day_local, periods):
    fetched_at = utc_now_naive()  # UTC-naiv
    conn = get_connection()
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
    day_local = today_local_date()

    # Standalone-läge: använd orchestratorns token + gql
    import orchestrator as orch

    pvl_b64 = os.getenv("ARRIGO_PVL_B64") or os.getenv("ARRIGO_PVL_PATH") or orch.PVL_B64
    ref_prefix = (os.getenv("ARRIGO_REF_PREFIX") or "Huvudcentral_C1").strip()
    prefix = os.getenv("ARRIGO_HEAT_PLAN_PREFIX") or f"{ref_prefix}.HEAT_PLAN"

    token = orch.arrigo_login()
    heat = read_heat_plan_96(orch.gql, token, pvl_b64, prefix=prefix)

    upsert_plan(site_code, plan_type, day_local, heat)

if __name__ == "__main__":
    main()
