from __future__ import annotations

from datetime import datetime

from smartweb_backend.db.connection import get_connection


def fetch_electricity_prices(utc_start: datetime, utc_end: datetime):
    """Fetch electricity prices for a UTC-naive window [utc_start, utc_end)."""

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT datetime, price
                FROM electricity_prices
                WHERE datetime >= %s AND datetime < %s
                ORDER BY datetime
                """,
                (utc_start, utc_end),
            )
            return cursor.fetchall()
    finally:
        conn.close()


def insert_ignore_electricity_prices(entries: list[tuple[datetime, float]]) -> int:
    """Insert electricity prices (UTC-naive) and ignore duplicates.

    Returns number of newly inserted rows.
    """

    if not entries:
        return 0

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.executemany(
                "INSERT IGNORE INTO electricity_prices (datetime, price) VALUES (%s, %s)",
                entries,
            )
        conn.commit()
        return int(conn.affected_rows())
    finally:
        conn.close()
