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

WANTED = [
  r"\.PI_PUSH_REQ$",
  r"\.PI_PUSH_ACK$",
  r"\.PI_PUSH_DAY$",
  r"\.TD_READY$",
  r"\.TM_READY$",
  r"\.VV_PLAN_CHANGED$",
  r"\.VV_PLAN_ACK$",
  r"\.HEAT_PLAN_CHANGED$",
  r"\.HEAT_PLAN_ACK$",
  r"\.(VV_PLAN|W_PLAN)\(\d+\)$",
  r"\.HEAT_PLAN\(\d+\)$",
]

def main():
    tok = arrigo_login(LOGIN_URL, USER, PASS, VERIFY)
    data = gql(GRAPHQL_URL, tok, Q, {"path": PVL_B64}, VERIFY)
    vars_list = (((data.get("data") or {}).get("data") or {}).get("variables")) or []

    tas = [v.get("technicalAddress") for v in vars_list if v.get("technicalAddress")]
    print(f"PVL vars: {len(tas)}")
    print("PVL_B64:", PVL_B64)

    for pat in WANTED:
        r = re.compile(pat)
        hits = [ta for ta in tas if r.search(ta)]
        print("\n==", pat, "==")
        if not hits:
            print("  (inga träffar)")
            continue
        # Sortera snyggt, särskilt för (0..95)
        def keyfn(s):
            m = re.search(r"\((\d+)\)$", s)
            return int(m.group(1)) if m else 10**9
        hits_sorted = sorted(hits, key=keyfn)
        for ta in hits_sorted[:50]:
            print(" ", ta)
        if len(hits_sorted) > 50:
            print(f"  ... ({len(hits_sorted)} träffar totalt)")

if __name__ == "__main__":
    main()
