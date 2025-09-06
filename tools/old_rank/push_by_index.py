#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, json
from datetime import datetime, date
import argparse

OLDRANK_DIR = "/home/runerova/smartweb/tools/old_rank"
sys.path.append(OLDRANK_DIR)
import exo_price_rank as old  # din befintliga, oförändrade kod

def get_index_map(graphql_url: str, token: str, pvl_b64: str, verify_tls: bool) -> dict:
    q = """
    query($path:String!){
      data(path:$path){
        variables { technicalAddress }
      }
    }
    """
    data = old.gql(graphql_url, token, q, {"path": pvl_b64}, verify_tls)
    # old.gql returnerar toppnivå "data"; vårt fält heter också "data" → två steg:
    vars_ = data["data"]["variables"]
    return { v["technicalAddress"]: i for i, v in enumerate(vars_) }

def build_writes_by_index(pvl_b64: str, site_id: str, payload: dict, idx: dict) -> list:
    pre = f"Huvudcentral_{site_id}"
    kv = []
    ta_ok = f"{pre}.PRICE_OK"
    if ta_ok in idx:
        kv.append({ "key": f"{pvl_b64}:{idx[ta_ok]}", "value": "0" })
    # klassiska PRICE_RANK_00..23
    for hour, val in enumerate(payload["price_rank"]):
        ta = f"{pre}.PRICE_RANK_{hour:02d}"
        if ta in idx:
            kv.append({ "key": f"{pvl_b64}:{idx[ta]}", "value": str(val) })
    # array PRICE_RANK(0)..(23) om de finns
    for hour, val in enumerate(payload["price_rank"]):
        ta = f"{pre}.PRICE_RANK({hour})"
        if ta in idx:
            kv.append({ "key": f"{pvl_b64}:{idx[ta]}", "value": str(val) })
    # masker och stamp (skrivs bara om de finns i PVL-listan)
    extras = {
        f"{pre}.EC_MASK_L":  payload["masks"]["EC"]["L"],
        f"{pre}.EC_MASK_H":  payload["masks"]["EC"]["H"],
        f"{pre}.EX_MASK_L":  payload["masks"]["EX"]["L"],
        f"{pre}.EX_MASK_H":  payload["masks"]["EX"]["H"],
        f"{pre}.PRICE_STAMP": payload["price_stamp"],
    }
    for ta, val in extras.items():
        if ta in idx:
            kv.append({ "key": f"{pvl_b64}:{idx[ta]}", "value": str(val) })
    if ta_ok in idx:
        kv.append({ "key": f"{pvl_b64}:{idx[ta_ok]}", "value": "1" })
    return kv

def main():
    ap = argparse.ArgumentParser(description="Push via PVL_B64:index med hjälp av old_rank-funktionerna.")
    ap.add_argument("--site-id", default="C1")
    ap.add_argument("--day", default="")
    ap.add_argument("--tz", default="Europe/Stockholm")
    ap.add_argument("--cheap-pct", type=float, default=-0.20)
    ap.add_argument("--exp-pct",   type=float, default=+0.20)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--login-url",   default=os.getenv("ARRIGO_LOGIN_URL",""))
    ap.add_argument("--graphql-url", default=os.getenv("ARRIGO_GRAPHQL_URL",""))
    ap.add_argument("--pvl-path",    default=os.getenv("ARRIGO_PVL_PATH",""))
    ap.add_argument("--arrigo-user", default=os.getenv("ARRIGO_USER","APIUser"))
    ap.add_argument("--arrigo-pass", default=os.getenv("ARRIGO_PASS","API_S#are"))
    ap.add_argument("--insecure",    action="store_true")
    args = ap.parse_args()

    if not args.login_url or not args.graphql_url:
        sys.exit("Saknar --login-url/--graphql-url (eller ARRIGO_LOGIN_URL/ARRIGO_GRAPHQL_URL).")
    if not args.pvl_path:
        sys.exit("Saknar --pvl-path (eller ARRIGO_PVL_PATH).")
    verify_tls = not (args.insecure or os.getenv("ARRIGO_INSECURE")=="1")

    token = old.arrigo_login(args.login_url, args.arrigo_user, args.arrigo_pass, verify_tls)

    if args.day:
        y,m,d = map(int, args.day.split("-")); day = date(y,m,d)
    else:
        day = datetime.now(old.STHLM).date()

    payload = old.build_payload_from_db(
        site_id=args.site_id, local_day=day, tzname=args.tz,
        cheap_pct=args.cheap_pct, exp_pct=args.exp_pct
    )

    idx = get_index_map(args.graphql_url, token, args.pvl_path, verify_tls)
    items = build_writes_by_index(args.pvl_path, args.site_id, payload, idx)
    if not items:
        sys.exit("Inga matchande nycklar hittades i PVL-listan.")

    mut_name, arg_name, input_type = old.discover_write_signature(args.graphql_url, token, verify_tls)
    mutation = f"mutation ($vars:[{input_type}!]!){{ {mut_name}({arg_name}:$vars) }}"

    data = old.gql(args.graphql_url, token, mutation, {"vars": items}, verify_tls)
    print(f"✅ Push skickad ({len(items)} nycklar). Svar: {json.dumps(data, ensure_ascii=False)}")

    if args.verify:
        q = """
        query($path:String!){
          data(path:$path){
            variables { technicalAddress value }
          }
        }
        """
        r = old.gql(args.graphql_url, token, q, {"path": args.pvl_path}, verify_tls)
        vars_ = r["data"]["variables"]
        pick = [v for v in vars_ if v["technicalAddress"].endswith(".PRICE_OK")]
        pick += [v for v in vars_ if ".PRICE_RANK_0" in v["technicalAddress"]]
        for v in sorted(pick, key=lambda x: x["technicalAddress"]):
            print(f"{v['technicalAddress']:<32} = {v['value']}")

if __name__ == "__main__":
    main()
