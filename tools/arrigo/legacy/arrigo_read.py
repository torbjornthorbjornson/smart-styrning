#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
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

def login():
    return arrigo_login(LOGIN_URL, USER, PASS, VERIFY)

def get_vars_list(token):
    r = gql(GRAPHQL_URL, token, Q, {"path": PVL_B64}, VERIFY)
    # robust extraction: return first list we find
    for candidate in (
        (((r.get("data") or {}).get("data") or {}).get("variables")),
        ((r.get("data") or {}).get("variables")),
        (r.get("variables")),
    ):
        if isinstance(candidate, list):
            return candidate
    raise RuntimeError(f"Could not locate variables list in response keys={list(r.keys()) if isinstance(r, dict) else type(r)}")

def get_vals_and_idx(token):
    vars_list = get_vars_list(token)
    vals = {}
    idx  = {}
    for i, v in enumerate(vars_list):
        ta = v.get("technicalAddress")
        if not ta:
            continue
        idx[ta] = i
        vals[ta] = v.get("value")
    return vals, idx, vars_list
