#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, base64
from push_from_db import build_verify, ensure_b64, gql, arrigo_login

LOGIN_URL   = os.getenv("ARRIGO_LOGIN_URL")
GRAPHQL_URL = os.getenv("ARRIGO_GRAPHQL_URL")
USER        = os.getenv("ARRIGO_USER")
PASS        = os.getenv("ARRIGO_PASS")

PVL_RAW = os.getenv("ARRIGO_PVL_B64") or os.getenv("ARRIGO_PVL_PATH")
PVL_ENS = ensure_b64(PVL_RAW)
VERIFY  = build_verify()

Q = """query($path:String!){
  data(path:$path){
    variables{ technicalAddress value }
  }
}"""

def b64decode(s):
    try:
        return base64.b64decode(s).decode("utf-8", "replace")
    except Exception as e:
        return f"<decode failed: {e}>"

def count_vars(path, tok):
    r = gql(GRAPHQL_URL, tok, Q, {"path": path}, VERIFY)

    # prova flera vanliga strukturer (vi vill bara se var datan faktiskt ligger)
    candidates = [
        (((r.get("data") or {}).get("data") or {}).get("variables")),
        ((r.get("data") or {}).get("variables")),
        (r.get("variables")),
    ]
    for c in candidates:
        if isinstance(c, list):
            return len(c), r
    return None, r

def main():
    tok = arrigo_login(LOGIN_URL, USER, PASS, VERIFY)

    print("PVL_RAW:", PVL_RAW)
    print("PVL_RAW decoded:", b64decode(PVL_RAW))
    print("PVL_ENS:", PVL_ENS)
    print("PVL_ENS decoded:", b64decode(PVL_ENS))
    print()

    n_raw, r_raw = count_vars(PVL_RAW, tok)
    print("count(PVL_RAW):", n_raw)

    n_ens, r_ens = count_vars(PVL_ENS, tok)
    print("count(PVL_ENS):", n_ens)

    # Om vi fortfarande inte hittar listan, dumpa nycklarna så vi ser hur gql() ser ut
    if n_raw is None and n_ens is None:
        print("\n--- Could not find variables list in response shape ---")
        print("Top keys:", list(r_ens.keys()) if isinstance(r_ens, dict) else type(r_ens))
        if isinstance(r_ens, dict) and "data" in r_ens:
            print("data keys:", list((r_ens.get("data") or {}).keys()))

if __name__ == "__main__":
    main()
