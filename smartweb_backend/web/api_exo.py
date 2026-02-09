from __future__ import annotations

import json
import os

from flask import Blueprint, Response, render_template, request

from smartweb_backend.services import exo_service
from smartweb_backend.db.connection import get_connection
from smartweb_backend.time_utils import today_local_date


bp = Blueprint("exo", __name__)


@bp.route("/exo", methods=["GET", "POST"])
def exo_console():
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
	)


@bp.route("/api/exo_payload/<site_code>")
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
