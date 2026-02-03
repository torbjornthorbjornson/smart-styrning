#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re
from push_from_db import build_verify, ensure_b64, gql, arrigo_login

LOGIN_URL   = os.getenv("ARRIGO_LOGIN_URL")
GRAPHQL_URL = os.getenv("ARRIGO_GRAPHQL_URL")
USER        = os.getenv("ARRIGO_USER")
PASS        = os.getenv("ARRIGO_PASS")

PVL_RAW = os.getenv("ARRIGO_PVL_B64") or os.getenv("ARRIGO_PVL_PATH")
PVL_B64 = ensure_b64(PVL_RAW)
VERIFY  = build_verify()

Q = """query($path:String!){
  data(path:$path){
    variables{ technicalAddress value }
  }
}"""

def main():
    tok = arrigo_login(LOGIN_URL, USER, PASS, VERIFY)
    data = gql(GRAPHQL_URL, tok, Q, {"path": PVL_B64}, VERIFY)

    vars_list = (((data.get("data") or {}).get("data") or {}).get("variables")) or []
    tas = [v.get("technicalAddress") for v in vars_list if v.get("technicalAddress")]

    print("PVL_B64:", PVL_B64)
    print("COUNT :", len(tas))

    # 1) Handshake: visa alla TA som innehåller dessa substrängar (oavsett prefix)
    keys = ["PI_PUSH_REQ","PI_PUSH_ACK","PI_PUSH_DAY","TD_READY","TM_READY",
            "VV_PLAN_CHANGED","VV_PLAN_ACK","HEAT_PLAN_CHANGED","HEAT_PLAN_ACK"]
    print("\n=== HANDSHAKE TA (contains) ===")
    for k in keys:
        hits = [ta for ta in tas if k in ta]
        print(f"{k}: {len(hits)}")
        for ta in hits[:20]:
            print(" ", ta)
        if len(hits) > 20:
            print("  ...")

    # 2) Arrays: allt som ser ut som NAME(n)
    arr = []
    for ta in tas:
        m = re.search(r"\((\d+)\)$", ta)
        if m:
            arr.append((ta, int(m.group(1))))
    print("\n=== ARRAYS (anything ending with (n)) ===")
    print("arrays:", len(arr))
    # grupper per basnamn (TA utan (n))
    groups = {}
    for ta, n in arr:
        base = re.sub(r"\(\d+\)$", "", ta)
        groups.setdefault(base, []).append(n)

    # sortera grupper efter storlek
    grp_sorted = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for base, idxs in grp_sorted[:40]:
        idxs_sorted = sorted(idxs)
        print(f"{base}  count={len(idxs_sorted)}  range={idxs_sorted[0]}..{idxs_sorted[-1]}")
    if len(grp_sorted) > 40:
        print(f"... ({len(grp_sorted)} grupper totalt)")

    # 3) Visa detaljer för de viktigaste plan-arrayerna om de finns
    print("\n=== LIKELY PLAN ARRAYS (filtered) ===")
    wanted_words = ["VV_PLAN", "W_PLAN", "HEAT_PLAN", "PRICE_RANK", "PRICE_VAL", "EC_MASK", "EX_MASK"]
    for w in wanted_words:
        hits = [base for base,_ in grp_sorted if w in base]
        print(w, ":", len(hits))
        for base in hits[:10]:
            idxs = sorted(groups[base])
            print(f"  {base}  count={len(idxs)}  range={idxs[0]}..{idxs[-1]}")
        if len(hits) > 10:
            print("  ...")

if __name__ == "__main__":
    main()
