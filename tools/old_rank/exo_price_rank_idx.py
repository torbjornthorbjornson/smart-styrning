#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, os
from datetime import datetime, date, time, timedelta
from typing import Dict, Any, Iterable, List, Tuple

import pytz, pymysql, requests

STHLM = pytz.timezone("Europe/Stockholm")
UTC   = pytz.UTC

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

# -------- Arrigo API helpers --------

def arrigo_login(login_url: str, user: str, password: str, verify_tls: bool) -> str:
    r = requests.post(login_url, json={"username": user, "password": password},
                      timeout=15, verify=verify_tls)
    r.raise_for_status()
    j = r.json()
    tok = j.get("authToken")
    if not tok:
        raise SystemExit(f"Inget authToken i svar: {j}")
    return tok

def gql(graphql_url: str, token: str, query: str, variables: Dict[str, Any], verify_tls: bool) -> Dict[str, Any]:
    r = requests.post(graphql_url,
                      headers={"Authorization": f"Bearer {token}"},
                      json={"query": query, "variables": variables},
                      timeout=30, verify=verify_tls)
    r.raise_for_status()
    j = r.json()
    if "errors" in j:
        raise SystemExit("GraphQL-fel: " + json.dumps(j["errors"], ensure_ascii=False))
    return j["data"]

def _unwrap_type(t):
    while t and t.get("ofType"):
        t = t["ofType"]
    return t

def discover_write_signature(graphql_url: str, token: str, verify_tls: bool):
    q = """
    query Introspect {
      __schema {
        mutationType {
          fields {
            name
            args {
              name
              type { kind name ofType { kind name ofType { kind name } } }
            }
          }
        }
      }
    }"""
    data = gql(graphql_url, token, q, {}, verify_tls)
    for f in data["__schema"]["mutationType"]["fields"]:
        if f["name"].startswith("write"):
            for a in f["args"]:
                if a["name"] in ("variables","vars","values","data"):
                    t = _unwrap_type(a["type"])
                    if t and t.get("kind") == "INPUT_OBJECT" and t.get("name"):
                        return f["name"], a["name"], t["name"]
    # fallback
    return "writeData", "variables", "VariableKeyValue"

def get_index_map(graphql_url: str, token: str, pvl_b64: str, verify_tls: bool) -> Dict[str,int]:
    q = """
    query($path:String!){
      data(path:$path){
        variables { technicalAddress }
      }
    }"""
    data = gql(graphql_url, token, q, {"path": pvl_b64}, verify_tls)
    vars_ = data["data"]["variables"] or []
    return { v["technicalAddress"]: i for i, v in enumerate(vars_) }

def build_writes_by_index_lists(pvl_b64: str, site_id: str, payload: dict, idx: Dict[str,int]):
    pre = f"Huvudcentral_{site_id}"

    def key_for(ta: str) -> str|None:
        if ta in idx:
            return f"{pvl_b64}:{idx[ta]}"
        return None

    ok_key = key_for(f"{pre}.PRICE_OK")

    # ranks
    bulk = []
    for h, val in enumerate(payload["price_rank"]):
        for ta in (f"{pre}.PRICE_RANK_{h:02d}", f"{pre}.PRICE_RANK({h})"):
            k = key_for(ta)
            if k: bulk.append({"key": k, "value": str(val)})

    # masks + stamp
    extras = [
        (f"{pre}.EC_MASK_L",   payload["masks"]["EC"]["L"]),
        (f"{pre}.EC_MASK_H",   payload["masks"]["EC"]["H"]),
        (f"{pre}.EX_MASK_L",   payload["masks"]["EX"]["L"]),
        (f"{pre}.EX_MASK_H",   payload["masks"]["EX"]["H"]),
        (f"{pre}.PRICE_STAMP", payload["price_stamp"]),
    ]
    for ta, val in extras:
        k = key_for(ta)
        if k: bulk.append({"key": k, "value": str(val)})

    ok0 = [{"key": ok_key, "value": "0"}] if ok_key else []
    ok1 = [{"key": ok_key, "value": "1"}] if ok_key else []
    return ok0, bulk, ok1

def push_to_arrigo_by_index(login_url: str, graphql_url: str,
                            user: str, password: str, pvl_path_b64: str,
                            payload: Dict[str, Any], verify_tls: bool):
    token = arrigo_login(login_url, user, password, verify_tls)
    mut_name, arg_name, input_type = discover_write_signature(graphql_url, token, verify_tls)
    mutation = f"mutation ($vars:[{input_type}]!){{ {mut_name}({arg_name}:$vars) }}"

    idx = get_index_map(graphql_url, token, pvl_path_b64, verify_tls)
    if not idx:
        raise SystemExit("Hittar inga variabler i PVL (fel path?).")

    ok0, bulk, ok1 = build_writes_by_index_lists(pvl_path_b64, payload["site_id"], payload, idx)

    # OK=0
    if ok0:
        gql(graphql_url, token, mutation, {"vars": ok0}, verify_tls)

    # allt
    if bulk:
        # Skicka i rimliga chunkar ifall listan blir lång
        CHUNK=40
        for i in range(0, len(bulk), CHUNK):
            gql(graphql_url, token, mutation, {"vars": bulk[i:i+CHUNK]}, verify_tls)

    # OK=1
    if ok1:
        gql(graphql_url, token, mutation, {"vars": ok1}, verify_tls)

# ---------------- CLI ----------------

def parse_args():
    ap = argparse.ArgumentParser(description="Bygg rank/masker från DB och pusha till Arrigo via <PVL_B64>:<index>.")
    ap.add_argument("--site-id", required=True)
    ap.add_argument("--day", help="YYYY-MM-DD (lokaldag). Default = idag.")
    ap.add_argument("--tz", default="Europe/Stockholm")
    ap.add_argument("--cheap-pct", type=float, default=-0.20)
    ap.add_argument("--exp-pct",   type=float, default=+0.20)

    ap.add_argument("--base")
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
    raise SystemExit("Ange --base ELLER både --login-url och --graphql-url.")

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
        if not args.pvl_path: raise SystemExit("Saknar --pvl-path (base64 PVL).")
        push_to_arrigo_by_index(login_url, graphql_url,
                                args.arrigo_user, args.arrigo_pass, args.pvl_path,
                                payload, verify_tls)
        print("Push klar (index-metoden).")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
