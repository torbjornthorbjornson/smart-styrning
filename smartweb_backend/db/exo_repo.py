from __future__ import annotations

from datetime import date

from smartweb_backend.db.connection import get_connection


def build_exo_payload(site_code: str, day_local: date, top_n: int, cheap_pct: float, exp_pct: float) -> None:
    """Execute stored procedure that builds payload rows in DB."""

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CALL exo_build_payload(%s,%s,%s,%s,%s)",
                (site_code, day_local, top_n, cheap_pct, exp_pct),
            )
        conn.commit()
    finally:
        conn.close()


def get_exo_payload_json(site_code: str, day_local: date):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload_json FROM exo_payloads WHERE site_code=%s AND day_local=%s",
                (site_code, day_local),
            )
            row = cur.fetchone()
            if row and row.get("payload_json"):
                return row["payload_json"]
            return None
    finally:
        conn.close()
