#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Listar vad din Project Builder "api"-sida exponerar (PVL variables).

Krav (env):
- ARRIGO_LOGIN_URL
- ARRIGO_GRAPHQL_URL
- ARRIGO_USER / ARRIGO_PASS
- ARRIGO_PVL_PATH (klartext) eller ARRIGO_PVL_B64

Exempel:
  set -a; source /home/runerova/.arrigo.env; set +a
  python3 list_pvl_vars.py --limit 200 --filter PRICE_

"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse

from smartweb_backend.clients import arrigo_client


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--filter", dest="filter_text", default="")
    ap.add_argument("--values", action="store_true", help="visa value-fältet också")
    args = ap.parse_args()

    cfg = arrigo_client.load_config()
    if not cfg.pvl_b64:
        raise SystemExit("Saknar ARRIGO_PVL_B64 / ARRIGO_PVL_PATH")

    print("PVL_RAW:", cfg.pvl_raw)
    print("PVL_B64:", cfg.pvl_b64)
    print("PVL_DECODED:", cfg.pvl_decoded)
    print()

    # Föredra orchestratorns token-cache om den finns, men tillåt fallback-login för CLI.
    vars_list = arrigo_client.read_pvl_variables(cfg, allow_login=True, prefer_token_cache=True)

    filter_text = (args.filter_text or "").strip().lower()
    out = []
    for v in vars_list:
        ta = str(v.get("technicalAddress") or "")
        if filter_text and filter_text not in ta.lower():
            continue
        out.append(v)

    out = out[: max(0, int(args.limit))]

    for i, v in enumerate(out):
        ta = str(v.get("technicalAddress") or "")
        if args.values:
            print(f"{i:04d}  {ta} = {v.get('value')}")
        else:
            print(f"{i:04d}  {ta}")

    print(f"\nCount total: {len(vars_list)}")
    print(f"Count shown: {len(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
