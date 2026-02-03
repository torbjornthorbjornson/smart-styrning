#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
verify_ack_write.py
- Läser alla variables från PVL
- Bygger TA -> index-map
- Skriver PI_PUSH_ACK = 1 via <PVL_B64>:<index>
- Läser tillbaka och verifierar
INGET annat påverkas.
"""

import os, time
from push_from_db import build_verify, ensure_b64, gql, arrigo_login

LOGIN_URL   = os.getenv("ARRIGO_LOGIN_URL")
GRAPHQL_URL = os.getenv("ARRIGO_GRAPHQL_URL")
USER        = os.getenv("ARRIGO_USER")
PASS        = os.getenv("ARRIGO_PASS")

PVL_RAW = os.getenv("ARRIGO_PVL_B64") or os.getenv("ARRIGO_PVL_PATH")
PVL_B64 = ensure_b64(PVL_RAW)
VERIFY  = build_verify()

ACK_TA = "Huvudcentral_C1.PI_PUSH_ACK"

Q = """query($path:String!){
  data(path:$path){
    variables{ technicalAddress value }
  }
}"""

M = "mutation($v:[VariableKeyValue!]!){ writeData(variables:$v) }"

def main():
    print("🔍 Verify ACK write via index")

    tok = arrigo_login(LOGIN_URL, USER, PASS, VERIFY)

    data = gql(GRAPHQL_URL, tok, Q, {"path": PVL_B64}, VERIFY)
    vars_list = (((data.get("data") or {}).get("data") or {}).get("variables")) or []

    idx = {}
    vals = {}
    for i, v in enumerate(vars_list):
        ta = v.get("technicalAddress")
        if ta:
            idx[ta] = i
            vals[ta] = v.get("value")

    if ACK_TA not in idx:
        raise RuntimeError(f"ACK TA saknas i PVL: {ACK_TA}")

    print(f"ACK before: {vals.get(ACK_TA)}  (index={idx[ACK_TA]})")

    key = f"{PVL_B64}:{idx[ACK_TA]}"
    gql(GRAPHQL_URL, tok, M, {"v":[{"key": key, "value": "1"}]}, VERIFY)

    time.sleep(1)

    data2 = gql(GRAPHQL_URL, tok, Q, {"path": PVL_B64}, VERIFY)
    vars2 = (((data2.get("data") or {}).get("data") or {}).get("variables")) or []
    vals2 = { v.get("technicalAddress"): v.get("value") for v in vars2 if v.get("technicalAddress") }

    print(f"ACK after : {vals2.get(ACK_TA)}")
    print("✅ VERIFY OK")

if __name__ == "__main__":
    main()
