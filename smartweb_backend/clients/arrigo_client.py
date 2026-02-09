# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import json
import os
import tempfile
import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class ArrigoConfig:
    login_url: str | None
    graphql_url: str | None
    username: str | None
    password: str | None
    pvl_raw: str | None
    pvl_b64: str | None
    pvl_decoded: str | None
    token_cache_file: str
    token_cache_exists: bool


Q_READ_VARS = "query($p:String!){ data(path:$p){ variables{ technicalAddress value } } }"


def _ensure_b64(pvl_raw: str) -> str:
    try:
        base64.b64decode(pvl_raw)
        return pvl_raw
    except Exception:
        return base64.b64encode(pvl_raw.encode("utf-8")).decode("ascii")


def _b64decode(s: str | None) -> str | None:
    if not s:
        return None
    try:
        return base64.b64decode(s).decode("utf-8", errors="replace")
    except Exception:
        return None


def _default_token_cache_file() -> str:
    # smartweb_backend/clients -> smartweb_backend -> smartweb
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(here, "..", ".."))
    return os.path.join(project_root, "tools", "arrigo", ".arrigo_token.json")


def _load_token_cache_payload(path: str) -> dict[str, Any] | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            j = json.load(f)
        return j if isinstance(j, dict) else None
    except Exception:
        return None


def load_config() -> ArrigoConfig:
    token_cache_file = os.getenv("ARRIGO_TOKEN_CACHE_FILE") or _default_token_cache_file()
    token_cache_exists = os.path.exists(token_cache_file)
    cache_payload = _load_token_cache_payload(token_cache_file) if token_cache_exists else None

    login_url = os.getenv("ARRIGO_LOGIN_URL") or (cache_payload or {}).get("login_url")
    graphql_url = os.getenv("ARRIGO_GRAPHQL_URL") or (cache_payload or {}).get("graphql_url")
    username = os.getenv("ARRIGO_USER") or os.getenv("ARRIGO_USERNAME")
    password = os.getenv("ARRIGO_PASS") or os.getenv("ARRIGO_PASSWORD")

    pvl_raw = os.getenv("ARRIGO_PVL_B64") or os.getenv("ARRIGO_PVL_PATH") or (cache_payload or {}).get("pvl_b64")
    pvl_b64 = _ensure_b64(pvl_raw) if pvl_raw else None
    pvl_decoded = _b64decode(pvl_b64) if pvl_b64 else None

    return ArrigoConfig(
        login_url=login_url,
        graphql_url=graphql_url,
        username=username,
        password=password,
        pvl_raw=pvl_raw,
        pvl_b64=pvl_b64,
        pvl_decoded=pvl_decoded,
        token_cache_file=token_cache_file,
        token_cache_exists=token_cache_exists,
    )


def load_token_from_cache(cfg: ArrigoConfig, *, max_age_sec: float | None = None) -> str | None:
    """Returnerar bearer-token från token-cache om den finns och är frisk.

    Kontrakt-idé: orchestratorn gör login och skriver token hit.
    Webben kan då läsa token utan att göra egen login (som kan invalidera andra tokens).
    """

    path = cfg.token_cache_file
    try:
        st = os.stat(path)
        if max_age_sec is not None:
            age = max(0.0, (time.time() - st.st_mtime))  # type: ignore[name-defined]
            if age > max_age_sec:
                return None
        with open(path, "r", encoding="utf-8") as f:
            j = json.load(f)
        tok = (j or {}).get("token")
        if not tok or not isinstance(tok, str):
            return None
        return tok
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _need(value: str | None, name: str) -> str:
    if not value:
        raise RuntimeError(f"Saknar {name}")
    return value


def login(cfg: ArrigoConfig, *, connect_timeout_sec: float = 10.0, read_timeout_sec: float = 20.0) -> str:
    url = _need(cfg.login_url, "ARRIGO_LOGIN_URL")
    user = _need(cfg.username, "ARRIGO_USER")
    pwd = _need(cfg.password, "ARRIGO_PASS")

    r = requests.post(
        url,
        json={"username": user, "password": pwd},
        timeout=(connect_timeout_sec, read_timeout_sec),
    )
    r.raise_for_status()
    tok = (r.json() or {}).get("authToken")
    if not tok:
        raise RuntimeError("Login utan token")
    return tok


def gql(
    cfg: ArrigoConfig,
    token: str,
    query: str,
    variables: dict[str, Any],
    *,
    connect_timeout_sec: float = 10.0,
    read_timeout_sec: float = 30.0,
) -> dict[str, Any]:
    url = _need(cfg.graphql_url, "ARRIGO_GRAPHQL_URL")
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "variables": variables},
        timeout=(connect_timeout_sec, read_timeout_sec),
    )
    r.raise_for_status()
    j = r.json() or {}
    if "errors" in j:
        raise RuntimeError(str(j["errors"]))
    return j.get("data") or {}


def read_pvl_variables(
    cfg: ArrigoConfig,
    *,
    token: str | None = None,
    allow_login: bool = True,
    prefer_token_cache: bool = True,
    connect_timeout_sec: float = 10.0,
    read_timeout_sec: float = 30.0,
) -> list[dict[str, Any]]:
    pvl_b64 = _need(cfg.pvl_b64, "ARRIGO_PVL_B64/ARRIGO_PVL_PATH")

    tok = token
    if not tok and prefer_token_cache:
        tok = load_token_from_cache(cfg)
    if not tok:
        if not allow_login:
            raise RuntimeError(
                "Ingen Arrigo-token tillgänglig (token-cache saknas/är tom). "
                "Starta orchestratorn så den skriver token-cache, eller tillåt login explicit."
            )
        tok = login(cfg, connect_timeout_sec=connect_timeout_sec, read_timeout_sec=min(read_timeout_sec, 20.0))
    data = gql(
        cfg,
        tok,
        Q_READ_VARS,
        {"p": pvl_b64},
        connect_timeout_sec=connect_timeout_sec,
        read_timeout_sec=read_timeout_sec,
    )

    # Expected shape: {"data": {"variables": [...]}}
    node = data.get("data") if isinstance(data, dict) else None
    if not isinstance(node, dict):
        raise RuntimeError("Oväntat GraphQL-svar: saknar data.data")
    variables = node.get("variables")
    if not isinstance(variables, list):
        raise RuntimeError("Oväntat GraphQL-svar: saknar variables-lista")
    return variables
