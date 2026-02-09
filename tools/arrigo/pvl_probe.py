#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import os
from typing import Optional


def ensure_b64(pvl_raw: str) -> str:
    if not pvl_raw:
        raise SystemExit("Saknar ARRIGO_PVL_B64 / ARRIGO_PVL_PATH")
    try:
        base64.b64decode(pvl_raw)
        return pvl_raw
    except Exception:
        return base64.b64encode(pvl_raw.encode("utf-8")).decode("ascii")


PVL_RAW = os.getenv("ARRIGO_PVL_B64") or os.getenv("ARRIGO_PVL_PATH")
PVL_ENS = ensure_b64(PVL_RAW) if PVL_RAW else None

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

def count_vars(gql_fn, token: str, path: str):
    r = gql_fn(token, Q, {"path": path})

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

def probe_pvl(gql_fn, token: str, pvl_raw: str, pvl_ens: Optional[str] = None):
    if not pvl_raw:
        raise SystemExit("Saknar ARRIGO_PVL_B64 / ARRIGO_PVL_PATH")
    pvl_ens = pvl_ens or ensure_b64(pvl_raw)

    print("PVL_RAW:", pvl_raw)
    print("PVL_RAW decoded:", b64decode(pvl_raw))
    print("PVL_ENS:", pvl_ens)
    print("PVL_ENS decoded:", b64decode(pvl_ens))
    print()

    n_raw, r_raw = count_vars(gql_fn, token, pvl_raw)
    print("count(PVL_RAW):", n_raw)

    n_ens, r_ens = count_vars(gql_fn, token, pvl_ens)
    print("count(PVL_ENS):", n_ens)

    # Om vi fortfarande inte hittar listan, dumpa nycklarna så vi ser hur gql() ser ut
    if n_raw is None and n_ens is None and isinstance(r_ens, dict):
        print("\n--- Could not find variables list in response shape ---")
        print("Top keys:", list(r_ens.keys()) if isinstance(r_ens, dict) else type(r_ens))
        if isinstance(r_ens, dict) and "data" in r_ens:
            print("data keys:", list((r_ens.get("data") or {}).keys()))


def main():
    import orchestrator as orch

    tok = orch.arrigo_login()
    probe_pvl(orch.gql, tok, PVL_RAW, PVL_ENS)

if __name__ == "__main__":
    main()
