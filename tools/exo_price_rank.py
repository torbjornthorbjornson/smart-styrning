#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, os, sys
from datetime import datetime, date, time, timedelta
from typing import Dict, Any, Iterable, List, Tuple

import pytz, pymysql, requests

STHLM = pytz.timezone("Europe/Stockholm")
UTC   = pytz.UTC

IDX_RANK_START = 0
IDX_EC_L = 24
IDX_EC_H = 25
IDX_EX_L = 26
IDX_EX_H = 27
IDX_STAMP = 28
IDX_OK = 29

def db():
    return pymysql.connect(
        read_default_file="/home/runerova/.my.cnf",
        database="smart_styrning",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

def local_day_to_utc_window(local_day: date, tzname: str):
    tz = pytz.timezone(tzname)
    local_midnight = tz.localize(datetime.combine(local_day, time(0,0)))
    start_utc = local_midnight.astimezone(UTC).replace(tzinfo=None)
    end_utc   = (local_midnight + timedelta(days=1)).astimezone(UTC).replace(tzinfo=None)
    return start_utc, end_utc

def pack_mask(hours: Iterable[int]) -> Tuple[int,int]:
    bits = 0
    for h in hours:
        if 0 <= h <= 23:
            bits |= (1 << h)
    return bits & 0xFFFF, (bits >> 16) & 0xFFFF

def normalize_to_24_hours(rows: List[Dict[str, Any]]) -> List[Tuple[int, float]]:
    per_hour = {h: [] for h in range(24)}
    for r in rows:
        dt_utc = UTC.localize(r["datetime"])
        h_loc  = dt_utc.astimezone(STHLM).hour
        per_hour[h_loc].append(float(r["price"]))
    out = []
    known = [h for h,v in per_hour.items() if v]
    if not known:
        raise SystemExit("Elpriser saknas för dygnet.")
    for h in range(24):
        vals = per_hour[h]
        if not vals:
            left = h-1
            while left >=0 and not per_hour[left]: left -= 1
            right = h+1
            while right <=23 and not per_hour[right]: right += 1
            if left >=0 and right <=23 and per_hour[left] and per_hour[right]:
                price = (sum(per_hour[left])/len(per_hour[left]) + sum(per_hour[right])/len(per_hour[right]))/2.0
            elif left >=0 and per_hour[left]:
                price = sum(per_hour[left])/len(per_hour[left])
            else:
                f = min(known); price = sum(per_hour[f])/len(per_hour[f])
        else:
            price = sum(vals)/len(vals)
        out.append((h, float(price)))
    return out

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

    hour_price = normalize_to_24_hours(rows)
    price_rank = [h for (h, _) in sorted(hour_price, key=lambda t: t[1])]
    if len(price_rank)!=24 or sorted(price_rank)!=list(range(24)):
        raise SystemExit("price_rank inte permutation av 0..23.")

    sorted_prices = sorted([p for (_,p) in hour_price])
    median = (sorted_prices[11] + sorted_prices[12]) / 2.0
    cheap_thr = median * (1.0 + cheap_pct)
    exp_thr   = median * (1.0 + exp_pct)

    cheap_hours = {h for (h,p) in hour_price if p <= cheap_thr}
    exp_hours   = {h for (h,p) in hour_price if p >= exp_thr}

    ecL, ecH = pack_mask(cheap_hours)
    exL, exH = pack_mask(exp_hours)

    return {
        "site_id": site_id,
        "day": local_day.strftime("%Y-%m-%d"),
        "tz": tzname,
        "price_stamp": int(local_day.strftime("%Y%m%d")),
        "price_rank": price_rank,
        "masks": {"EC":{"L":ecL,"H":ecH}, "EX":{"L":exL,"H":exH}},
        "meta": {
            "generated_at": datetime.now(UTC).astimezone(STHLM).isoformat(timespec="seconds"),
            "median": median, "cheap_thr": cheap_thr, "exp_thr": exp_thr,
            "cheap_pct": cheap_pct, "exp_pct": exp_pct,
        },
    }

# ---------------- Arrigo API ----------------

def arrigo_login(login_url: str, user: str, password: str, verify_tls: bool) -> str:
    r = requests.post(login_url, json={"username": user, "password": password},
                      timeout=15, verify=verify_tls)
    try:
        r.raise_for_status()
    except requests.HTTPError:
        raise SystemExit(f"Inloggning misslyckades ({r.status_code}): {r.text}")
    j = r.json()
    tok = j.get("authToken")
    if not tok:
        raise SystemExit(f"Inget authToken i svar: {j}")
    return tok

def gql(graphql_url: str, token: str, query: str, variables: Dict[str, Any], verify_tls: bool) -> Dict[str, Any]:
    r = requests.post(graphql_url,
                      headers={"Authorization": f"Bearer {token}"},
                      json={"query": query, "variables": variables},
                      timeout=20, verify=verify_tls)
    try:
        r.raise_for_status()
    except requests.HTTPError:
        raise SystemExit(f"GraphQL HTTP-fel ({r.status_code}): {r.text}")
    j = r.json()
    if "errors" in j:
        raise SystemExit("GraphQL-fel: " + json.dumps(j["errors"], ensure_ascii=False))
    return j["data"]

def _unwrap_type(t):
    while t and t.get("ofType"):
        t = t["ofType"]
    return t

def discover_write_signature(graphql_url: str, token: str, verify_tls: bool):
    """
    Introspektera schema → hitta mutationen som skriver PVL.
    Vi letar efter ett fält som heter 'writeData' (vanligast).
    Om inte, tar vi första mutation med en argument-lista som heter något likt 'variables'
    och vars typ är en LIST med INPUT_OBJECT.
    Returnerar (mutation_name, argument_name, input_type_name)
    """
    q = """
    query Introspect {
      __schema {
        mutationType {
          name
          fields {
            name
            args {
              name
              type { kind name ofType { kind name ofType { kind name } } }
            }
          }
        }
      }
    }
    """
    data = gql(graphql_url, token, q, {}, verify_tls)
    mtype = data["__schema"].get("mutationType")
    if not mtype:
        raise SystemExit("Hittar ingen mutationType i schemat (är skrivning avstängd?).")
    fields = mtype["fields"] or []

    # 1) försök hitta "writeData" direkt
    for f in fields:
        if f["name"] == "writeData":
            for a in f["args"]:
                if a["name"] in ("variables","vars","values","data"):
                    t = _unwrap_type(a["type"])
                    if t and t.get("kind") == "INPUT_OBJECT" and t.get("name"):
                        return f["name"], a["name"], t["name"]

    # 2) fallback – första fält med en 'variables'-liknande arg som tar INPUT_OBJECT-lista
    for f in fields:
        for a in f["args"]:
            if a["name"] in ("variables","vars","values","data"):
                t = _unwrap_type(a["type"])
                if t and t.get("kind") == "INPUT_OBJECT" and t.get("name"):
                    return f["name"], a["name"], t["name"]

    # 3) hård fallback – prova vanliga namn
    return "writeData", "variables", "WriteVariableInput"

def build_writes_for_pvl(pvl_path: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    w = []
    for rank, hour in enumerate(payload["price_rank"]):
        w.append({"key": f"{pvl_path}:{IDX_RANK_START+rank}", "value": str(hour)})
    w += [
        {"key": f"{pvl_path}:{IDX_EC_L}", "value": str(payload["masks"]["EC"]["L"])},
        {"key": f"{pvl_path}:{IDX_EC_H}", "value": str(payload["masks"]["EC"]["H"])},
        {"key": f"{pvl_path}:{IDX_EX_L}", "value": str(payload["masks"]["EX"]["L"])},
        {"key": f"{pvl_path}:{IDX_EX_H}", "value": str(payload["masks"]["EX"]["H"])},
        {"key": f"{pvl_path}:{IDX_STAMP}", "value": str(payload["price_stamp"])},
    ]
    return w

def push_to_arrigo(login_url: str, graphql_url: str,
                   user: str, password: str, pvl_path: str,
                   payload: Dict[str, Any], verify_tls: bool):
    token = arrigo_login(login_url, user, password, verify_tls)

    # Auto-detektera rätt mutation, argument och input-typ
    mut_name, arg_name, input_type = discover_write_signature(graphql_url, token, verify_tls)
    mutation = f"mutation ($vars:[{input_type}!]!){{ {mut_name}({arg_name}:$vars) }}"

    # OK=0
    gql(graphql_url, token, mutation, {"vars":[{"key":f"{pvl_path}:{IDX_OK}","value":"0"}]}, verify_tls)
    # värden
    gql(graphql_url, token, mutation, {"vars": build_writes_for_pvl(pvl_path, payload)}, verify_tls)
    # OK=1
    gql(graphql_url, token, mutation, {"vars":[{"key":f"{pvl_path}:{IDX_OK}","value":"1"}]}, verify_tls)

def verify_readback(login_url: str, graphql_url: str, user: str, password: str,
                    pvl_path: str, verify_tls: bool) -> Dict[str, Any]:
    token = arrigo_login(login_url, user, password, verify_tls)
    q = 'query ($path:String!){ data(path:$path){ variables { technicalAddress value } } }'
    return gql(graphql_url, token, q, {"path": pvl_path}, verify_tls)

# ---------------- CLI ----------------

def parse_args():
    ap = argparse.ArgumentParser(description="Bygg rank/masker från DB och (valfritt) pusha till Arrigo.")
    ap.add_argument("--site-id", required=True)
    ap.add_argument("--day", help="YYYY-MM-DD (lokaldag). Default = idag.")
    ap.add_argument("--tz", default="Europe/Stockholm")
    ap.add_argument("--cheap-pct", type=float, default=-0.20)
    ap.add_argument("--exp-pct",   type=float, default=+0.20)

    ap.add_argument("--base", help="Bas-URL utan /login eller /graphql")
    ap.add_argument("--login-url")
    ap.add_argument("--graphql-url")

    ap.add_argument("--arrigo-user", default=os.getenv("ARRIGO_USER", "APIUser"))
    ap.add_argument("--arrigo-pass", default=os.getenv("ARRIGO_PASS", "API_S#are"))
    ap.add_argument("--pvl-path",    default=os.getenv("ARRIGO_PVL_PATH", ""))
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--insecure", action="store_true")
    return ap.parse_args()

def resolve_urls(args):
    if args.base:
        base = args.base.rstrip("/")
        return f"{base}/login", f"{base}/graphql"
    if args.login_url and args.graphql_url:
        return args.login_url, args.graphql_url
    raise SystemExit("Ange --base (utan /login|/graphql) ELLER båda --login-url och --graphql-url.")

def main():
    args = parse_args()
    login_url, graphql_url = resolve_urls(args)
    verify_tls = not args.insecure
    local_day = date.fromisoformat(args.day) if args.day else datetime.now(STHLM).date()

    payload = build_payload_from_db(
        site_id=args.site_id, local_day=local_day, tzname=args.tz,
        cheap_pct=args.cheap_pct, exp_pct=args.exp_pct
    )

    if args.out:
        js = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out == "-": print(js)
        else:
            with open(args.out, "w", encoding="utf-8") as f: f.write(js)

    if args.push:
        if not args.pvl_path: raise SystemExit("Saknar --pvl-path (base64).")
        push_to_arrigo(login_url, graphql_url,
                       args.arrigo_user, args.arrigo_pass, args.pvl_path,
                       payload, verify_tls)
        print("Push klar (OK=0 → värden → OK=1).")

    if args.verify:
        data = verify_readback(login_url, graphql_url,
                               args.arrigo_user, args.arrigo_pass, args.pvl_path,
                               verify_tls)
        print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
