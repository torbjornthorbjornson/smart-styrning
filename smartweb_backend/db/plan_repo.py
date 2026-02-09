from __future__ import annotations

import json
from datetime import date

from smartweb_backend.db.connection import get_connection


def db_read_plan(site_code: str, plan_type: str, day_local: date):
    """Read latest cached plan (96 periods) from arrigo_plan_cache.

    Returns:
      - list on success
      - None if no plan exists
    """

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT periods
                FROM arrigo_plan_cache
                WHERE site_code=%s AND plan_type=%s AND day_local=%s
                ORDER BY fetched_at DESC
                LIMIT 1
                """,
                (site_code, plan_type, day_local),
            )
            row = cur.fetchone()
            if not row:
                return None
            return json.loads(row["periods"])
    finally:
        conn.close()
