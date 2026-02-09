from __future__ import annotations

from smartweb_backend.db.connection import get_connection


def fetch_latest_water_status():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM water_status ORDER BY timestamp DESC LIMIT 1")
            return cursor.fetchone()
    finally:
        conn.close()
