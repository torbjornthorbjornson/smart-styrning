from __future__ import annotations

from smartweb_backend.db.connection import get_connection


def get_site(site_code: str):
    """Return a site row (dict) or None."""

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT site_code, tz, default_topn FROM sites WHERE site_code=%s LIMIT 1",
                (site_code,),
            )
            return cur.fetchone()
    finally:
        conn.close()
