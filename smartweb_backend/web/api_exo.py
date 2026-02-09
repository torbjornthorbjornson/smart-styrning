from __future__ import annotations

import hmac
import json
import os
from functools import wraps

from flask import Blueprint, Response, render_template, request

from smartweb_backend.clients import arrigo_client
from smartweb_backend.services import exo_service
from smartweb_backend.db.connection import get_connection
from smartweb_backend.time_utils import today_local_date


bp = Blueprint("exo", __name__)


def _admin_creds() -> tuple[str, str] | None:
	user = (os.environ.get("SMARTWEB_ADMIN_USER") or "").strip()
	password = os.environ.get("SMARTWEB_ADMIN_PASS") or ""
	if not user or not password:
		return None
	return user, password


def _unauthorized() -> Response:
	return Response(
		"Authentication required",
		status=401,
		headers={"WWW-Authenticate": 'Basic realm="Smartweb"'},
	)


def require_admin(view_func):
	@wraps(view_func)
	def wrapper(*args, **kwargs):
		creds = _admin_creds()
		if creds is None:
			return view_func(*args, **kwargs)
		user, password = creds
		auth = request.authorization
		if not auth or auth.type != "basic":
			return _unauthorized()
		if not hmac.compare_digest(auth.username or "", user):
			return _unauthorized()
		if not hmac.compare_digest(auth.password or "", password):
			return _unauthorized()
		return view_func(*args, **kwargs)

	return wrapper


@bp.route("/exo", methods=["GET", "POST"])
@require_admin
def exo_console():
	admin_enabled = _admin_creds() is not None
	site_codes: list[str] = []
	try:
		conn = get_connection()
		try:
			with conn.cursor() as cur:
				cur.execute("SELECT site_code FROM sites ORDER BY site_code")
				site_codes = [row["site_code"] for row in cur.fetchall()]
		finally:
			conn.close()
	except Exception:
		# Keep page available even if DB is temporarily down.
		site_codes = []

	exo_url = os.environ.get("EXO_URL")
	has_token = bool(os.environ.get("EXO_TOKEN"))

	# Arrigo (Project Builder / api-sida -> PVL)
	arrigo_cfg = arrigo_client.load_config()
	arrigo_has_pvl = bool(arrigo_cfg.pvl_b64)
	arrigo_token_cache_file = arrigo_cfg.token_cache_file
	arrigo_token_cache_exists = arrigo_cfg.token_cache_exists

	arrigo_filter = (request.values.get("arrigo_filter") or "").strip()
	arrigo_limit = int((request.values.get("arrigo_limit") or "200").strip() or 200)
	arrigo_show_values = str(request.values.get("arrigo_show_values") or "").lower() in ("1", "true", "yes", "on")
	arrigo_total = 0
	arrigo_vars: list[dict[str, str]] = []
	arrigo_error = ""

	selected_site = (request.values.get("site_code") or "").strip() or (site_codes[0] if site_codes else "")
	day_str = (request.values.get("day") or "").strip() or today_local_date().strftime("%Y-%m-%d")
	build = str(request.values.get("build", "0")).lower() in ("1", "true", "yes", "on")

	n_arg = (request.values.get("n") or "").strip() or None
	cheap_arg = (request.values.get("cheap_pct") or "").strip() or None
	exp_arg = (request.values.get("exp_pct") or "").strip() or None

	action = (request.values.get("action") or "").strip().lower()

	result_obj = None
	result_json = ""
	status_msg = ""
	error_msg = ""

	if request.method == "POST" and action:
		# Arrigo: lista PVL-variabler (kräver ingen site / EXO).
		if action == "arrigo_list":
			try:
				# Kontrakt: orchestratorn sköter login. Webben ska inte göra egen login (kan invalidera token).
				vars_list = arrigo_client.read_pvl_variables(arrigo_cfg, allow_login=False, prefer_token_cache=True)
				arrigo_total = len(vars_list)
				flt = arrigo_filter.lower()
				filtered = []
				for v in vars_list:
					ta = str(v.get("technicalAddress") or "")
					if flt and flt not in ta.lower():
						continue
					row = {"technicalAddress": ta}
					if arrigo_show_values:
						row["value"] = "" if v.get("value") is None else str(v.get("value"))
					filtered.append(row)
				arrigo_vars = filtered[: max(0, arrigo_limit)]
				status_msg = f"Arrigo: läste {arrigo_total} variabler." if not status_msg else status_msg
			except Exception as e:
				arrigo_error = f"Arrigo-fel: {e}"
		else:
			if not selected_site:
				error_msg = "Ingen site vald (och kunde inte läsa sites från DB)."
				return render_template(
					"exo.html",
					site_codes=site_codes,
					selected_site=selected_site,
					day_str=day_str,
					n_arg=n_arg or "",
					cheap_arg=cheap_arg or "",
					exp_arg=exp_arg or "",
					build=build,
					exo_url=exo_url,
					has_token=has_token,
					status_msg=status_msg,
					error_msg=error_msg,
					result_json=result_json,
					arrigo_has_pvl=arrigo_has_pvl,
					arrigo_token_cache_file=arrigo_token_cache_file,
					arrigo_token_cache_exists=arrigo_token_cache_exists,
					arrigo_pvl_decoded=arrigo_cfg.pvl_decoded or "",
					arrigo_filter=arrigo_filter,
					arrigo_limit=arrigo_limit,
					arrigo_show_values=arrigo_show_values,
					arrigo_total=arrigo_total,
					arrigo_vars=arrigo_vars,
					arrigo_error=arrigo_error,
				)
			try:
				day_local = exo_service.resolve_day_local(day_str)
				params = exo_service.build_params(selected_site, day_local, n_arg, cheap_arg, exp_arg)
				exo_service.maybe_build_payload(params, build=build)
				payload_json = exo_service.fetch_payload_json(params)

				if action == "preview":
					result_obj = json.loads(payload_json)
					status_msg = "Payload hämtad."
				elif action == "dry_run":
					result_obj = {
						"dry_run": True,
						"target": {"exo_url": exo_url, "has_token": has_token},
						"payload": json.loads(payload_json),
					}
					status_msg = "Dry-run: inget skickades."
				elif action == "push":
					confirm = (request.form.get("confirm") or "").strip().upper()
					if confirm != "PUSH":
						error_msg = "Skriv PUSH i bekräftelserutan för att skicka."
					else:
						timeout_sec = int((request.values.get("timeout") or "20").strip())
						push_result = exo_service.push_payload(payload_json, exo_url=exo_url, token=os.environ.get("EXO_TOKEN"), timeout_sec=timeout_sec)
						if isinstance(push_result, exo_service.ExoPushHttpError):
							result_obj = {
								"sent": False,
								"http_status": push_result.http_status,
								"error": push_result.error,
								"body": push_result.body,
							}
							error_msg = "EXO svarade med HTTP-fel (proxy 502)."
						else:
							http_status, body = push_result
							result_obj = {"sent": True, "http_status": http_status, "exo_response": body}
							status_msg = "Skickat till EXO."
				else:
					error_msg = f"Okänd action: {action}"

			except exo_service.InvalidDayFormatError as e:
				error_msg = str(e)
			except exo_service.MissingExoUrlError as e:
				error_msg = str(e)
			except exo_service.UnknownSiteError as e:
				error_msg = str(e)
			except exo_service.PayloadNotFoundError:
				error_msg = "Payload saknas för dag (testa Build först)."
			except Exception as e:
				error_msg = f"Fel: {e}"

	if result_obj is not None:
		result_json = json.dumps(result_obj, ensure_ascii=False, indent=2)

	return render_template(
		"exo.html",
		admin_enabled=admin_enabled,
		site_codes=site_codes,
		selected_site=selected_site,
		day_str=day_str,
		n_arg=n_arg or "",
		cheap_arg=cheap_arg or "",
		exp_arg=exp_arg or "",
		build=build,
		exo_url=exo_url,
		has_token=has_token,
		status_msg=status_msg,
		error_msg=error_msg,
		result_json=result_json,
		arrigo_has_pvl=arrigo_has_pvl,
		arrigo_token_cache_file=arrigo_token_cache_file,
		arrigo_token_cache_exists=arrigo_token_cache_exists,
		arrigo_pvl_decoded=arrigo_cfg.pvl_decoded or "",
		arrigo_filter=arrigo_filter,
		arrigo_limit=arrigo_limit,
		arrigo_show_values=arrigo_show_values,
		arrigo_total=arrigo_total,
		arrigo_vars=arrigo_vars,
		arrigo_error=arrigo_error,
	)


@bp.route("/api/exo_payload/<site_code>")
@require_admin
def api_exo_payload(site_code: str):
	day_str = request.args.get("day")
	try:
		day_local = exo_service.resolve_day_local(day_str)
	except exo_service.InvalidDayFormatError as e:
		return Response(json.dumps({"error": str(e)}), status=400, mimetype="application/json")

	build = exo_service.parse_bool(request.args.get("build", "0"), truthy=("1", "true", "yes"))
	n_arg = request.args.get("n")
	cheap_arg = request.args.get("cheap_pct")
	exp_arg = request.args.get("exp_pct")

	try:
		params = exo_service.build_params(site_code, day_local, n_arg, cheap_arg, exp_arg)
		exo_service.maybe_build_payload(params, build=build)
		payload_json = exo_service.fetch_payload_json(params)
		return Response(payload_json, mimetype="application/json")
	except exo_service.UnknownSiteError as e:
		return Response(json.dumps({"error": str(e)}), status=404, mimetype="application/json")
	except exo_service.PayloadNotFoundError:
		return Response(
			json.dumps({"error": "payload not found for day; try with build=1"}),
			status=404,
			mimetype="application/json",
		)
	except Exception as e:
		msg = str(e).replace('"', "\\\"")
		return Response(f'{{"error":"{msg}"}}', status=500, mimetype="application/json")


@bp.route("/api/exo_push/<site_code>", methods=["GET", "POST"])
def api_exo_push(site_code: str):
	day_str = request.args.get("day")
	try:
		day_local = exo_service.resolve_day_local(day_str)
	except exo_service.InvalidDayFormatError as e:
		return Response(json.dumps({"error": str(e)}), status=400, mimetype="application/json")

	build = exo_service.parse_bool(request.args.get("build", "0"), truthy=("1", "true", "yes", "on"))
	dry_run = exo_service.parse_bool(request.args.get("dry_run", "0"), truthy=("1", "true", "yes", "on"))
	timeout_sec = int(request.args.get("timeout", "20"))

	n_arg = request.args.get("n")
	cheap_arg = request.args.get("cheap_pct")
	exp_arg = request.args.get("exp_pct")

	exo_url = request.args.get("exo_url") or os.environ.get("EXO_URL")
	token = request.args.get("token") or os.environ.get("EXO_TOKEN")
	if not exo_url:
		return Response(
			json.dumps({"error": "EXO_URL saknas (ange ?exo_url=... eller sätt env EXO_URL)"}, ensure_ascii=False),
			status=400,
			mimetype="application/json",
		)

	try:
		params = exo_service.build_params(site_code, day_local, n_arg, cheap_arg, exp_arg)
		exo_service.maybe_build_payload(params, build=build)
		payload_json = exo_service.fetch_payload_json(params)
	except exo_service.UnknownSiteError as e:
		return Response(json.dumps({"error": str(e)}), status=404, mimetype="application/json")
	except exo_service.PayloadNotFoundError:
		return Response(
			json.dumps({"error": "payload not found for day; try build=1"}),
			status=404,
			mimetype="application/json",
		)
	except Exception as e:
		msg = str(e).replace('"', "\\\"")
		return Response(f'{{"error":"{msg}"}}', status=500, mimetype="application/json")

	if dry_run:
		return Response(
			json.dumps(
				{
					"dry_run": True,
					"target": {"exo_url": exo_url, "has_token": bool(token)},
					"payload": json.loads(payload_json),
				},
				ensure_ascii=False,
			),
			mimetype="application/json",
		)

	try:
		push_result = exo_service.push_payload(payload_json, exo_url=exo_url, token=token, timeout_sec=timeout_sec)
		if isinstance(push_result, exo_service.ExoPushHttpError):
			msg = {"sent": False, "http_status": push_result.http_status, "error": push_result.error, "body": push_result.body}
			return Response(json.dumps(msg, ensure_ascii=False), status=502, mimetype="application/json")

		status, body = push_result
		return Response(
			json.dumps(
				{
					"sent": True,
					"http_status": status,
					"exo_response": body,
					"site_id": site_code,
					"day": day_local.strftime("%Y-%m-%d"),
				},
				ensure_ascii=False,
			),
			mimetype="application/json",
		)
	except exo_service.MissingExoUrlError as e:
		return Response(json.dumps({"error": str(e)}, ensure_ascii=False), status=400, mimetype="application/json")
	except Exception as e:
		msg = {"sent": False, "error": str(e)}
		return Response(json.dumps(msg, ensure_ascii=False), status=502, mimetype="application/json")
