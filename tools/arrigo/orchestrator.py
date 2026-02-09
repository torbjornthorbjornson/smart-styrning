#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import _bootstrap  # noqa: F401

import argparse
import os
import time
from datetime import datetime, date, timedelta, time as dtime
import json
import tempfile
import requests
import base64
import re

from smartweb_backend.db.prices_repo import (
    fetch_electricity_prices,
    debug_electricity_prices_table,
)

from smartweb_backend.time_utils import (
    today_local_date,
    local_day_to_utc_window,
)

from push_from_db import (
    build_rank_and_masks,
    daily_avg_oat,
    push_to_arrigo,
)


# ==================================================
# TIDSZONER – FACIT
# ==================================================
# MariaDB lagrar electricity_prices.datetime som UTC (naiv DATETIME).
# spotpris.py skriver UTC som kan spänna över två kalenderdygn.
#
# Orchestratorn definierar ett LOKALT svenskt dygn (Europe/Stockholm)
# och översätter detta till ett UTC-fönster vid DB-frågor.
#
# Detta är ENDA platsen där lokal ↔ UTC-konvertering sker.
# Se: TODO/016_TIME_CONTRACT/README.md

# Konverteringen implementeras i smartweb_backend.time_utils för att delas mellan web/agent.


# ==================================================
# ARRIGO / EXOL – KONFIG
# ==================================================
LOGIN_URL   = os.getenv("ARRIGO_LOGIN_URL")
GRAPHQL_URL = os.getenv("ARRIGO_GRAPHQL_URL")
USER        = os.getenv("ARRIGO_USER") or os.getenv("ARRIGO_USERNAME")
PASS        = os.getenv("ARRIGO_PASS") or os.getenv("ARRIGO_PASSWORD")

PVL_RAW = os.getenv("ARRIGO_PVL_B64") or os.getenv("ARRIGO_PVL_PATH")
if not PVL_RAW:
    raise SystemExit("Saknar ARRIGO_PVL_B64 / ARRIGO_PVL_PATH")

# säkerställ base64 (Arrigo kräver detta)
try:
    base64.b64decode(PVL_RAW)
    PVL_B64 = PVL_RAW
except Exception:
    PVL_B64 = base64.b64encode(PVL_RAW.encode("utf-8")).decode("ascii")


def debug_log_pvl():
    """Loggar PVL (både raw och base64-decoded) för att säkerställa att vi läser rätt objekt i Arrigo."""
    if os.getenv("ARRIGO_DEBUG_TAS", "0") != "1":
        return
    try:
        decoded = base64.b64decode(PVL_B64).decode("utf-8", errors="replace")
    except Exception:
        decoded = "<kunde inte base64-dekoda PVL_B64>"
    log(f"🧾 PVL_RAW={PVL_RAW!r}")
    log(f"🧾 PVL_B64(decoded)={decoded!r}")

REF_PREFIX = (os.getenv("ARRIGO_REF_PREFIX") or "Huvudcentral_C1").strip()
TA_REQ = f"{REF_PREFIX}.PI_PUSH_REQ"
TA_ACK = f"{REF_PREFIX}.PI_PUSH_ACK"
TA_DAY = f"{REF_PREFIX}.PI_PUSH_DAY"
TA_TD_READY = f"{REF_PREFIX}.TD_READY"
TA_TM_READY = f"{REF_PREFIX}.TM_READY"

Q_READ  = "query($p:String!){ data(path:$p){ variables{ technicalAddress value } } }"
M_WRITE = "mutation($v:[VariableKeyValue!]!){ writeData(variables:$v) }"


# ==================================================
# INFRA
# ==================================================
SLEEP_SEC = float(os.getenv("ARRIGO_SLEEP_SEC", "4"))
REPUSH_COOLDOWN_SEC = float(os.getenv("ARRIGO_REPUSH_COOLDOWN_SEC", "120"))
EMPTY_DB_SLEEP_SEC = float(os.getenv("ARRIGO_EMPTY_DB_SLEEP_SEC", "60"))

# HTTP / nät
HTTP_CONNECT_TIMEOUT_SEC = float(os.getenv("ARRIGO_HTTP_CONNECT_TIMEOUT_SEC", "10"))
HTTP_READ_TIMEOUT_SEC = float(os.getenv("ARRIGO_HTTP_READ_TIMEOUT_SEC", "30"))
HTTP_LOGIN_TIMEOUT_SEC = float(os.getenv("ARRIGO_HTTP_LOGIN_TIMEOUT_SEC", "20"))
NET_BACKOFF_MAX_SEC = float(os.getenv("ARRIGO_NET_BACKOFF_MAX_SEC", "120"))

# Plan-cache (Arrigo -> MariaDB) via samma poll-loop (ingen cron).
PLAN_CACHE_ENABLE = os.getenv("ARRIGO_PLAN_CACHE_ENABLE", "1") == "1"
PLAN_CACHE_INTERVAL_SEC = float(os.getenv("ARRIGO_PLAN_CACHE_INTERVAL_SEC", "300"))


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def _default_token_cache_file() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, ".arrigo_token.json")


def write_token_cache(token: str) -> None:
    """Skriv bearer-token till cache-fil för att andra processer (t.ex. web UI) kan återanvända den.

    Viktigt för kontraktet: orchestratorn sköter login så att flera logins inte invaliderar varandras tokens.
    """

    path = os.getenv("ARRIGO_TOKEN_CACHE_FILE") or _default_token_cache_file()
    payload = {
        "token": token,
        "ts": time.time(),
        "login_url": LOGIN_URL,
        "graphql_url": GRAPHQL_URL,
        "pvl_b64": PVL_B64,
    }
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".arrigo_token.", suffix=".tmp", dir=os.path.dirname(path) or None)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            os.replace(tmp, path)
            try:
                os.chmod(path, 0o600)
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
    except Exception as e:
        log(f"⚠️ Kunde inte skriva token-cache: {e.__class__.__name__}: {e}")


def to_int(x, default=0):
    if isinstance(x, bool):
        return 1 if x else 0
    try:
        return int(float(x))
    except Exception:
        return default


def maybe_cache_plans_to_db(vals) -> None:
    """Cache:a HEAT_PLAN/VV_PLAN i MariaDB baserat på redan lästa PVL-variabler.

    Viktigt: inga skrivningar tillbaka till Arrigo här (endast DB).
    """

    if not PLAN_CACHE_ENABLE:
        return

    # Lazy imports så orchestratorn kan gå även om workers saknas.
    try:
        from readback_heatplan_to_db import extract_heat_plan_96, upsert_plan as upsert_heat
        from readback_vvplan_to_db import extract_plan_96 as extract_vv_plan_96, upsert_plan as upsert_vv
    except Exception as e:
        log(f"⚠️ Plan-cache: kunde inte importera readback-workers: {e.__class__.__name__}: {e}")
        return

    site_code = os.getenv("SITE_CODE", "HALTORP244")
    ref_prefix = (os.getenv("ARRIGO_REF_PREFIX") or "Huvudcentral_C1").strip()

    # Triggers (om de finns) – om EXOL pulserar dessa vill vi cache:a snabbt.
    ta_heat_changed = f"{ref_prefix}.HEAT_PLAN_CHANGED"
    ta_vv_changed = f"{ref_prefix}.VV_PLAN_CHANGED"

    heat_changed = to_int(vals.get(ta_heat_changed), default=0) == 1
    vv_changed = to_int(vals.get(ta_vv_changed), default=0) == 1

    # Prefixar för plan-variablerna
    heat_prefix = os.getenv("ARRIGO_HEAT_PLAN_PREFIX") or f"{ref_prefix}.HEAT_PLAN"
    vv_prefix = os.getenv("ARRIGO_VV_PLAN_PREFIX") or f"{ref_prefix}.VV_PLAN"

    day_local = today_local_date()

    def is_plan_value_ta(prefix: str, ta: str) -> bool:
        if not ta.startswith(prefix):
            return False
        # undvik "...HEAT_PLAN_CHANGED" etc
        if ta.endswith("_CHANGED") or ta.endswith("_ACK"):
            return False
        # Format A: PREFIX(5)
        if re.search(r"\((\d{1,2})\)\s*$", ta):
            return True
        # Format B: PREFIX_05_00:00
        tail = ta[len(prefix):]
        return re.search(r"_(\d{2})_", tail) is not None

    # Bara om vi ser att plan-variablerna faktiskt finns i PVL.
    # (Undvik att skriva 96x0 när det inte finns någon plan i Arrigo-objektet.)
    has_heat_any = any(is_plan_value_ta(heat_prefix, k) for k in vals.keys())
    has_vv_any = any(is_plan_value_ta(vv_prefix, k) for k in vals.keys())

    if heat_changed and not has_heat_any:
        log("⚠️ Plan-cache: HEAT_PLAN_CHANGED=1 men inga HEAT_PLAN-perioder hittades i PVL")
    if vv_changed and not has_vv_any:
        log("⚠️ Plan-cache: VV_PLAN_CHANGED=1 men inga VV_PLAN-perioder hittades i PVL")

    if has_heat_any:
        heat = extract_heat_plan_96(vals, prefix=heat_prefix)
        upsert_heat(site_code, "HEAT_PLAN", day_local, heat)

    if has_vv_any:
        vv = extract_vv_plan_96(vals, prefix=vv_prefix)
        upsert_vv(site_code, "VV_PLAN", day_local, vv)



# ==================================================
# ARRIGO API – HJÄLPARE
# ==================================================
def arrigo_login():
    r = requests.post(
        LOGIN_URL,
        json={"username": USER, "password": PASS},
        timeout=(HTTP_CONNECT_TIMEOUT_SEC, HTTP_LOGIN_TIMEOUT_SEC),
    )
    r.raise_for_status()
    tok = r.json().get("authToken")
    if not tok:
        raise RuntimeError("Login utan token")
    return tok


def ensure_token_cache_present(token: str) -> None:
    """Säkerställ att token-cache finns på disk.

    Om orchestratorn har en giltig token men cachefilen saknas (t.ex. om den blivit raderad),
    skriv om den så webben kan läsa utan egen login.
    """

    path = os.getenv("ARRIGO_TOKEN_CACHE_FILE") or _default_token_cache_file()
    if os.path.exists(path):
        return
    write_token_cache(token)


def gql(token, query, variables):
    r = requests.post(
        GRAPHQL_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "variables": variables},
        timeout=(HTTP_CONNECT_TIMEOUT_SEC, HTTP_READ_TIMEOUT_SEC),
    )
    r.raise_for_status()
    j = r.json()
    if "errors" in j:
        raise RuntimeError(j["errors"])
    return j["data"]


def sleep_backoff(current_sec: float) -> float:
    """Sleep for current backoff seconds and return next backoff (capped)."""
    time.sleep(current_sec)
    return min(max(SLEEP_SEC, current_sec) * 2.0, NET_BACKOFF_MAX_SEC)


def relogin_with_backoff(start_backoff_sec: float) -> str:
    backoff = max(SLEEP_SEC, start_backoff_sec)
    while True:
        try:
            tok = arrigo_login()
            log("🔐 Inloggad mot Arrigo")
            write_token_cache(tok)
            return tok
        except requests.exceptions.RequestException as e:
            log(f"🌐 Login nätverksfel: {e.__class__.__name__}: {e}")
            backoff = sleep_backoff(backoff)



def read_vals_and_idx(token):
    data = gql(token, Q_READ, {"p": PVL_B64})
    vars_list = data["data"]["variables"]
    vals, idx = {}, {}
    for i, v in enumerate(vars_list):
        ta = v["technicalAddress"]
        vals[ta] = v.get("value")
        idx[ta] = i
    return vals, idx


def write_ack(token, idx, value):
    key = f"{PVL_B64}:{idx[TA_ACK]}"
    gql(token, M_WRITE, {"v": [{"key": key, "value": str(value)}]})


def write_var(token, idx, technical_address: str, value: str):
    if technical_address not in idx:
        return False
    key = f"{PVL_B64}:{idx[technical_address]}"
    gql(token, M_WRITE, {"v": [{"key": key, "value": str(value)}]})
    return True


def diag_write_var(token, idx, technical_address: str, value: str):
    """Diagnostisk engångsskrivning för att verifiera att vi kan påverka en signal."""
    if technical_address not in idx:
        log(f"🧪 DIAG: TA saknas i idx: {technical_address}")
        return
    key = f"{PVL_B64}:{idx[technical_address]}"
    gql(token, M_WRITE, {"v": [{"key": key, "value": value}]})
    log(f"🧪 DIAG: wrote {technical_address} = {value!r}")


# ==================================================
# DB → PRISER
# ==================================================
def db_fetch_prices_for_day(day_local: date):
    utc_start, utc_end = local_day_to_utc_window(day_local)

    return fetch_electricity_prices(utc_start, utc_end)


def db_debug_prices_table():
    """Returnerar enkel status för electricity_prices (min/max/count).

    Körs endast vid behov (t.ex. när vi får 0 rader) och är tänkt som felsökningshjälp.
    """
    return debug_electricity_prices_table()


# ==================================================
# MAIN – ORCHESTRATOR
# ==================================================
def main():
    token = relogin_with_backoff(SLEEP_SEC)
    log("🔌 Orchestrator startad")
    log("🚨 ORCHESTRATOR VERSION 2026-02-08 20:45 🚨")
    write_token_cache(token)
    debug_log_pvl()
    if os.getenv("ARRIGO_DEBUG_TAS", "0") == "1":
        log(f"🧷 REF_PREFIX={REF_PREFIX!r}")
        log(f"🧷 TA_REQ={TA_REQ}")
        log(f"🧷 TA_ACK={TA_ACK}")
        log(f"🧷 TA_DAY={TA_DAY}")

    last_req = last_ack = last_day = object()
    last_req_raw = object()
    did_diag_req_write = False
    last_handled = {}  # request_key -> epoch seconds (endast efter lyckad push+ACK)
    last_plan_cache_ts = 0.0
    net_backoff_sec = max(SLEEP_SEC, 1.0)

    while True:
        try:
            ensure_token_cache_present(token)
            vals, idx = read_vals_and_idx(token)
            net_backoff_sec = max(SLEEP_SEC, 1.0)  # reset on success

            # Arrigo-planer -> DB (utan cron). Kör på intervall och även på CHANGED-puls.
            now_ts = time.time()
            should_cache = (now_ts - last_plan_cache_ts) >= PLAN_CACHE_INTERVAL_SEC
            ref_prefix = (os.getenv("ARRIGO_REF_PREFIX") or "Huvudcentral_C1").strip()
            heat_changed_ta = f"{ref_prefix}.HEAT_PLAN_CHANGED"
            vv_changed_ta = f"{ref_prefix}.VV_PLAN_CHANGED"
            if should_cache or to_int(vals.get(heat_changed_ta)) == 1 or to_int(vals.get(vv_changed_ta)) == 1:
                maybe_cache_plans_to_db(vals)
                last_plan_cache_ts = now_ts

            req_raw = vals.get(TA_REQ)
            if req_raw != last_req_raw:
                log(f"RAW PI_PUSH_REQ = {req_raw}")
                last_req_raw = req_raw
            if TA_REQ not in vals:
                 log(f"❌ TA_REQ saknas! keys={list(vals.keys())[:10]} ...")
            else:
                 log(f"✅ TA_REQ hittad, raw={vals[TA_REQ]!r}, type={type(vals[TA_REQ])}")

            if os.getenv("ARRIGO_DEBUG_TAS", "0") == "1":
                cands = []
                for k, v in vals.items():
                    if "PI_PUSH_REQ" in k or k.endswith(".PI_PUSH_REQ"):
                        cands.append((k, v))
                if cands:
                    log("🧭 PI_PUSH_REQ candidates:")
                    for k, v in sorted(cands):
                        log(f"    {k} = {v!r} ({type(v)})")

                # EXOL statusflaggor som styr request-kontrollern
                for suffix in ("TD_READY", "TM_READY", "DIAG_PUSH", "PI_PUSH_DAY"):
                    for k, v in vals.items():
                        if k.endswith(f".{suffix}"):
                            log(f"🧭 {suffix}: {k} = {v!r} ({type(v)})")
                            break

            # Diagnostik: försök sätta REQ via API (engång) och se om den studsar tillbaka.
            if os.getenv("ARRIGO_DIAG_SET_REQ", "0") == "1" and not did_diag_req_write:
                diag_write_var(token, idx, TA_REQ, "1")
                did_diag_req_write = True

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                log("🔑 401 → relogin")
                token = relogin_with_backoff(net_backoff_sec)
                write_token_cache(token)
                net_backoff_sec = max(SLEEP_SEC, 1.0)
                continue
            raise
        except requests.exceptions.RequestException as e:
            # Nätverksfel (timeout/DNS/connection reset). Orchestratorn ska fortsätta poll:a.
            log(f"🌐 Arrigo nätverksfel: {e.__class__.__name__}: {e}")
            net_backoff_sec = sleep_backoff(net_backoff_sec)
            continue
        except KeyboardInterrupt:
            raise
        except Exception as e:
            # Sista skyddsnät: logga och fortsätt. (Undvik att daemon dör pga transient eller oväntad data.)
            log(f"💥 Oväntat fel i poll-loop: {e.__class__.__name__}: {e}")
            time.sleep(SLEEP_SEC)
            continue

        req = to_int(vals.get(TA_REQ))
        ack = to_int(vals.get(TA_ACK))
        day = to_int(vals.get(TA_DAY))

        if (req, ack, day) != (last_req, last_ack, last_day):
            log(f"REQ={req} ACK={ack} DAY={day}")
            last_req, last_ack, last_day = req, ack, day

        # ==================================================
        # BESLUT: SKA NYA PRISER PUSHAS TILL ARRIGO?
        # ==================================================
        if req == 1 and ack == 0:

            target_day = today_local_date() + timedelta(days=day)
            log(f"📥 EXOL begär priser för lokalt dygn: {target_day}")

            request_key = f"{target_day.isoformat()}|DAY={day}"
            now_ts = time.time()
            last_ts = last_handled.get(request_key)
            if last_ts is not None and (now_ts - last_ts) < REPUSH_COOLDOWN_SEC:
                log(f"🕒 Request redan hanterad nyligen ({int(now_ts - last_ts)}s) → skip")
                time.sleep(SLEEP_SEC)
                continue

            rows = db_fetch_prices_for_day(target_day)
            log(f"📊 DB-perioder: {len(rows)}")

            # Om DB saknar priser (oftast för imorgon innan importen är klar):
            # pusha inte nollor och ACK:a inte, annars tror EXOL att den fått giltig data.
            if not rows:
                # Extra felsökning vid 0 rader: visa exakt UTC-fönster och tabellens täckning.
                utc_start, utc_end = local_day_to_utc_window(target_day)
                log(f"⏳ Inga priser i DB ännu → skippar push/ACK (UTC-fönster {utc_start} .. {utc_end})")
                if os.getenv("ARRIGO_DB_DEBUG", "0") == "1":
                    try:
                        st = db_debug_prices_table()
                        log(
                            "🧾 electricity_prices: "
                            f"cnt={st.get('cnt')} min_dt={st.get('min_dt')} max_dt={st.get('max_dt')}"
                        )
                    except Exception as e:
                        log(f"🧾 DB-debug misslyckades: {e.__class__.__name__}: {e}")
                # För imorgon (eller om importen dröjer) vill vi inte spamma Arrigo/DB.
                time.sleep(max(SLEEP_SEC, EMPTY_DB_SLEEP_SEC))
                continue

            rank, ec_masks, ex_masks, slot_price = build_rank_and_masks(rows)
            oat_yday = daily_avg_oat(target_day - timedelta(days=1))
            oat_tmr  = daily_avg_oat(target_day + timedelta(days=1))

            log("📤 Pushar till Arrigo")
            try:
                push_to_arrigo(
                    gql,
                    token,
                    PVL_B64,
                    rank,
                    ec_masks,
                    ex_masks,
                    target_day,
                    oat_yday,
                    oat_tmr,
                    slot_price,
                )
                write_ack(token, idx, 1)

                # Valfritt men ofta nödvändigt: tala om för EXOL att data för dagen nu är redo.
                # Detta driver request-controllern (PI_PUSH_REQ) via TD_READY/TM_READY.
                if os.getenv("ARRIGO_SET_READY", "1") == "1":
                    try:
                        if day == 0:
                            if write_var(token, idx, TA_TD_READY, "1"):
                                log("✅ TD_READY satt")
                        elif day == 1:
                            if write_var(token, idx, TA_TM_READY, "1"):
                                log("✅ TM_READY satt")
                    except Exception as e:
                        log(f"⚠️ Kunde inte sätta READY-flagga: {e.__class__.__name__}: {e}")

                last_handled[request_key] = time.time()
                log("✅ PI_PUSH_ACK satt")
            except requests.exceptions.RequestException as e:
                log(f"🌐 Arrigo nätverksfel under push: {e.__class__.__name__}: {e}")
                net_backoff_sec = sleep_backoff(net_backoff_sec)
                continue
            except Exception as e:
                log(f"❌ Push misslyckades: {e.__class__.__name__}: {e}")
                time.sleep(SLEEP_SEC)
                continue

        time.sleep(SLEEP_SEC)


def run_readback_plans(token: str, do_heat: bool, do_vv: bool):
    site_code = os.getenv("SITE_CODE", "HALTORP244")
    ref_prefix = (os.getenv("ARRIGO_REF_PREFIX") or "Huvudcentral_C1").strip()

    if do_heat:
        from readback_heatplan_to_db import read_heat_plan_96, upsert_plan

        prefix = os.getenv("ARRIGO_HEAT_PLAN_PREFIX") or f"{ref_prefix}.HEAT_PLAN"
        heat = read_heat_plan_96(gql, token, PVL_B64, prefix=prefix)
        day_local = today_local_date()
        upsert_plan(site_code, "HEAT_PLAN", day_local, heat)

    if do_vv:
        from readback_vvplan_to_db import read_vv_plan_96, upsert_plan

        prefix = os.getenv("ARRIGO_VV_PLAN_PREFIX") or f"{ref_prefix}.VV_PLAN"
        vv = read_vv_plan_96(gql, token, PVL_B64, prefix=prefix)
        day_local = today_local_date()
        upsert_plan(site_code, "VV_PLAN", day_local, vv)
    return


# ==================================================
# ENTRYPOINT
# ==================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--readback-heatplan", action="store_true", help="Läs HEAT_PLAN(0..95) och spara i DB, kör en gång och avsluta")
    ap.add_argument("--readback-vvplan", action="store_true", help="Läs VV_PLAN(0..95) och spara i DB, kör en gång och avsluta")
    args = ap.parse_args()

    if args.readback_heatplan or args.readback_vvplan:
        tok = arrigo_login()
        write_token_cache(tok)
        run_readback_plans(tok, do_heat=args.readback_heatplan, do_vv=args.readback_vvplan)
    else:
        backoff_sec = max(SLEEP_SEC, 1.0)
        while True:
            try:
                main()
                backoff_sec = max(SLEEP_SEC, 1.0)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                log(f"💥 Fatalt fel i main(): {e.__class__.__name__}: {e}")
                backoff_sec = sleep_backoff(backoff_sec)
