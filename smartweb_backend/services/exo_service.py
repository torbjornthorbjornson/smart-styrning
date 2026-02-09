from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime

from smartweb_backend.db.exo_repo import build_exo_payload, get_exo_payload_json
from smartweb_backend.db.sites_repo import get_site
from smartweb_backend.time_utils import today_local_date


class ExoServiceError(Exception):
	pass


class InvalidDayFormatError(ExoServiceError):
	pass


class UnknownSiteError(ExoServiceError):	pass


class PayloadNotFoundError(ExoServiceError):	pass


class MissingExoUrlError(ExoServiceError):	pass


@dataclass(frozen=True)
class ExoParams:
	site_code: str
	day_local: date
	top_n: int
	cheap_pct: float
	exp_pct: float


def resolve_day_local(day_str: str | None) -> date:
	if not day_str:
		return today_local_date()
	try:
		return datetime.strptime(day_str, "%Y-%m-%d").date()
	except ValueError as e:
		raise InvalidDayFormatError("invalid day format, use YYYY-MM-DD") from e


def parse_bool(v: str | None, *, truthy: tuple[str, ...]) -> bool:
	if v is None:
		return False
	return str(v).lower() in truthy


def build_params(
	site_code: str,
	day_local: date,
	n_arg: str | None,
	cheap_arg: str | None,
	exp_arg: str | None,
) -> ExoParams:
	site = get_site(site_code)
	if not site:
		raise UnknownSiteError("unknown site")

	top_n = int(n_arg) if n_arg is not None else int(site["default_topn"])
	cheap_pct = float(cheap_arg) if cheap_arg is not None else -0.30
	exp_pct = float(exp_arg) if exp_arg is not None else 0.50

	return ExoParams(site_code=site_code, day_local=day_local, top_n=top_n, cheap_pct=cheap_pct, exp_pct=exp_pct)


def maybe_build_payload(params: ExoParams, *, build: bool) -> None:
	if not build:
		return
	build_exo_payload(params.site_code, params.day_local, params.top_n, params.cheap_pct, params.exp_pct)


def fetch_payload_json(params: ExoParams) -> str:
	payload_json = get_exo_payload_json(params.site_code, params.day_local)
	if not payload_json:
		raise PayloadNotFoundError("payload not found for day")
	return payload_json


def post_to_exo(payload_json: str, exo_url: str, token: str | None = None, timeout: int = 20) -> tuple[int, str]:
	data = payload_json.encode("utf-8")
	req = urllib.request.Request(exo_url, data=data, method="POST", headers={"Content-Type": "application/json"})
	if token:
		req.add_header("Authorization", f"Bearer {token}")
	with urllib.request.urlopen(req, timeout=timeout) as resp:
		status = resp.status
		body = resp.read().decode("utf-8", "ignore")[:2000]
	return status, body


@dataclass(frozen=True)
class ExoPushHttpError:
	http_status: int
	error: str
	body: str


def push_payload(payload_json: str, *, exo_url: str | None, token: str | None, timeout_sec: int) -> tuple[int, str] | ExoPushHttpError:
	if not exo_url:
		raise MissingExoUrlError("EXO_URL saknas (ange ?exo_url=... eller sätt env EXO_URL)")

	try:
		return post_to_exo(payload_json, exo_url, token, timeout=timeout_sec)
	except urllib.error.HTTPError as e:
		body = e.read().decode("utf-8", "ignore") if hasattr(e, "read") else ""
		return ExoPushHttpError(http_status=e.code, error=str(e), body=body[:2000])
