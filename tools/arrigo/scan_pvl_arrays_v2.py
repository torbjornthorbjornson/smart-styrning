#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from arrigo_read import login, get_vars_list

def main():
    tok = login()
    vars_list = get_vars_list(tok)
    tas = [v.get("technicalAddress") for v in vars_list if v.get("technicalAddress")]

    print("COUNT:", len(tas))

    # Handshake contains-scan (prefixoberoende)
    keys = ["PI_PUSH_REQ","PI_PUSH_ACK","PI_PUSH_DAY","TD_READY","TM_READY",
            "VV_PLAN_CHANGED","VV_PLAN_ACK","HEAT_PLAN_CHANGED","HEAT_PLAN_ACK"]
    print("\n=== HANDSHAKE (contains) ===")
    for k in keys:
        hits = [ta for ta in tas if k in ta]
        print(f"{k}: {len(hits)}")
        for ta in hits[:10]:
            print(" ", ta)

    # Arrays: allt som slutar med (n)
    arr = []
    for ta in tas:
        m = re.search(r"\((\d+)\)$", ta)
        if m:
            arr.append((re.sub(r"\(\d+\)$", "", ta), int(m.group(1))))

    print("\n=== ARRAYS ===")
    print("arrays:", len(arr))

    groups = {}
    for base, n in arr:
        groups.setdefault(base, []).append(n)

    grp_sorted = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for base, idxs in grp_sorted[:30]:
        idxs = sorted(idxs)
        print(f"{base}  count={len(idxs)}  range={idxs[0]}..{idxs[-1]}")

    # Visa särskilt intressanta
    print("\n=== LIKELY ===")
    for w in ["W_PLAN", "VV_PLAN", "HEAT_PLAN", "PRICE_RANK", "PRICE_VAL", "EC_MASK", "EX_MASK"]:
        hits = [base for base,_ in grp_sorted if w in base]
        print(w, ":", len(hits))
        for base in hits[:10]:
            idxs = sorted(groups[base])
            print(f"  {base} count={len(idxs)} range={idxs[0]}..{idxs[-1]}")

if __name__ == "__main__":
    main()
