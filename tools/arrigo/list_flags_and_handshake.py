#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from arrigo_read import login, get_vars_list

NEED = [
  "PI_PUSH_REQ","PI_PUSH_ACK","PI_PUSH_DAY","TD_READY","TM_READY",
  "VV_PLAN_CHANGED","VV_PLAN_ACK","HEAT_PLAN_CHANGED","HEAT_PLAN_ACK",
]

def main():
    tok = login()
    vars_list = get_vars_list(tok)
    tas = [v.get("technicalAddress") for v in vars_list if v.get("technicalAddress")]

    print("=== EXACT MATCH (endswith) ===")
    for k in NEED:
        hits = [ta for ta in tas if ta.endswith("." + k)]
        print(f"{k}: {len(hits)}")
        for ta in hits:
            print(" ", ta)

    print("\n=== CONTAINS (fallback) ===")
    for k in NEED:
        hits = [ta for ta in tas if k in ta]
        print(f"{k}: {len(hits)}")
        for ta in hits[:20]:
            print(" ", ta)
        if len(hits) > 20:
            print("  ...")

if __name__ == "__main__":
    main()
