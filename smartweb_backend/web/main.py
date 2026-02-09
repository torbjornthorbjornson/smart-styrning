from __future__ import annotations

import math
import os
import subprocess
from datetime import datetime, timedelta

from flask import Blueprint, redirect, render_template, request, url_for
from smartweb_backend.db.plan_repo import db_read_plan
from smartweb_backend.db.water_repo import fetch_latest_water_status
from smartweb_backend.services.elprisvader_service import build_elpris_vader_view
from smartweb_backend.services.prices_service import build_daily_price_view
from smartweb_backend.services.utfall_service import aggregate_plans, build_utfall_bar_colors
from smartweb_backend.time_utils import today_local_date, utc_naive_to_local_label

bp = Blueprint("main", __name__)


SMARTWEB_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@bp.app_template_filter("svtid")
def svtid(dt_utc_naive):
    try:
        return utc_naive_to_local_label(dt_utc_naive)
    except Exception:
        return ""


@bp.route("/")
def home():
    return render_template("home.html")


@bp.route("/styrning")
def styrning():
    selected_date_str = request.args.get("datum")
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    else:
        selected_date = today_local_date()

    try:
        top_n = int(request.args.get("n", "4"))
    except ValueError:
        top_n = 4
    if top_n < 1:
        top_n = 1

    try:
        view = build_daily_price_view(selected_date, top_n=top_n)
        return render_template(
            "styrning.html",
            selected_date=selected_date,
            labels=view.labels,
            values=view.values,
            gräns=view.threshold,
            no_price=view.no_price,
            top_n=top_n,
            selected_labels_chrono=view.selected_labels_chrono,
            sorted_by_price=view.sorted_by_price,
            bar_colors=view.bar_colors,
        )
    except Exception as e:
        return f"Fel vid hämtning av elprisdata: {e}"


@bp.route("/haltorp244/utfall")
def haltorp244_utfall():
    selected_date_str = request.args.get("datum")
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    else:
        selected_date = today_local_date()

    heat_plan_96 = db_read_plan("HALTORP244", "HEAT_PLAN", selected_date) or [0] * 96
    vv_plan_96 = db_read_plan("HALTORP244", "VV_PLAN", selected_date) or [0] * 96
    plans = aggregate_plans(heat_plan_96, vv_plan_96)

    try:
        top_n = int(request.args.get("n", "4"))
    except ValueError:
        top_n = 4
    if top_n < 1:
        top_n = 1

    try:
        view = build_daily_price_view(selected_date, top_n=top_n)

        bar_colors = []
        if not view.no_price:
            bar_colors = build_utfall_bar_colors(len(view.values), plans)

        return render_template(
            "haltorp244_utfall.html",
            selected_date=selected_date,
            labels=view.labels,
            values=view.values,
            gräns=view.threshold,
            no_price=view.no_price,
            top_n=top_n,
            selected_labels_chrono=view.selected_labels_chrono,
            sorted_by_price=view.sorted_by_price,
            bar_colors=bar_colors,
            heat_ones=plans.heat_ones,
            vv_ones=plans.vv_ones,
            heat_plan_24=plans.heat_plan_24,
            vv_plan_24=plans.vv_plan_24,
        )

    except Exception as e:
        return f"Fel vid hämtning av elprisdata (Hältorp 244): {e}"


@bp.route("/vision")
def vision():
    return render_template("vision.html")


@bp.route("/dokumentation")
def dokumentation():
    return render_template("dokumentation.html")


@bp.route("/roadmap")
def roadmap():
    return render_template("roadmap.html")


@bp.route("/github_versions")
def github_versions():
    try:
        git_path = "/usr/bin/git"
        tags = subprocess.check_output([git_path, "tag", "--sort=-creatordate"], cwd=SMARTWEB_ROOT).decode().splitlines()
        tag_data = []
        for tag in tags:
            message = subprocess.check_output([git_path, "tag", "-n100", tag], cwd=SMARTWEB_ROOT).decode().strip()
            date_s = subprocess.check_output([git_path, "log", "-1", "--format=%cd", tag], cwd=SMARTWEB_ROOT).decode().strip()
            tag_data.append({"name": tag, "message": message, "date": date_s})
        return render_template("github_versions.html", tags=tag_data)
    except Exception as e:
        return f"Fel vid hämtning av git-taggar: {e}"


@bp.route("/gitlog")
def gitlog():
    try:
        logs = subprocess.check_output(
            ["/usr/bin/git", "log", "--pretty=format:%h - %s (%cr)"],
            cwd=SMARTWEB_ROOT,
            text=True,
        ).splitlines()
    except Exception as e:
        logs = [f"❌ Kunde inte läsa gitlog: {e}"]
    return render_template("gitlog.html", log="\n".join(logs))


@bp.route("/elprisvader")
def elprisvader():
    selected_date_str = request.args.get("datum")
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    else:
        selected_date = today_local_date()

    try:
        view = build_elpris_vader_view(selected_date)
        return render_template(
            "elpris_vader.html",
            selected_date=selected_date,
            weatherdata=view.weather_data,
            elprisdata=view.elpris_data,
            labels=view.labels,
            temperature=view.temperature,
            vind=view.vind,
            elpris_labels=view.elpris_labels,
            elpris_values=view.elpris_values,
            medel_temperature=view.medel_temperature,
            medel_vind=view.medel_vind,
            medel_elpris=view.medel_elpris,
            fallback_used=False,
            weather_date=selected_date,
        )

    except Exception as e:
        return f"Fel vid hämtning av väder/elprisdata: {e}"


@bp.route("/create_backup_tag", methods=["POST"])
def create_backup_tag():
    try:
        comment = request.form.get("comment", "").strip()
        now = datetime.now().strftime("%Y%m%d_%H%M")
        tag_name = f"backup_{now}"
        message = f"🔖 Manuell backup {now}" + (f": {comment}" if comment else "")
        subprocess.check_call(["/usr/bin/git", "tag", "-a", tag_name, "-m", message], cwd=SMARTWEB_ROOT)
        return redirect(url_for("main.github_versions"))
    except Exception as e:
        return f"Fel vid skapande av git-tag: {e}"


@bp.route("/restore_version", methods=["POST"])
def restore_version():
    try:
        tag = request.form.get("tag", "").strip()
        if not tag:
            return "Ingen tagg angiven för återställning."

        now = datetime.now().strftime("%Y%m%d_%H%M")
        backup_tag = f"pre_restore_{tag}_{now}"
        subprocess.check_call(
            ["/usr/bin/git", "tag", "-a", backup_tag, "-m", f"Säkerhetskopia före återställning av {tag}"],
            cwd=SMARTWEB_ROOT,
        )
        subprocess.check_call(["/usr/bin/git", "reset", "--hard", tag], cwd=SMARTWEB_ROOT)
        return redirect(url_for("main.restore_result", tag=tag, backup=backup_tag))
    except Exception as e:
        return f"Fel vid återställning: {e}"


@bp.route("/restore_result")
def restore_result():
    tag = request.args.get("tag")
    backup_tag = request.args.get("backup")
    return render_template("restore_result.html", tag=tag, backup_tag=backup_tag)


MAX_VOLYM = 10000


@bp.route("/vattenstyrning")
def vattenstyrning():
    latest = {}

    row = fetch_latest_water_status()
    if row:
        latest = {
            "nivå": row["level_liters"],
            "nivå_procent": round(row["level_liters"] / MAX_VOLYM * 100),
            "tryck": row["system_pressure"],
            "p1": row["pump1_freq"],
            "p2": row["pump2_freq"],
            "p3": row["pump3_freq"],
            "booster": row.get("booster_freq", 0.0),
            "flow_p1": row.get("flow_p1", 0.0),
            "flow_p2": row.get("flow_p2", 0.0),
            "flow_p3": row.get("flow_p3", 0.0),
            "flow_booster": row.get("flow_booster", 0.0),
        }

    return render_template("vattenstyrning.html", data=latest, cos=math.cos, sin=math.sin)
