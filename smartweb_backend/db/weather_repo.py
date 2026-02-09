from __future__ import annotations

from datetime import datetime

from smartweb_backend.db.connection import get_connection


def fetch_weather(utc_start: datetime, utc_end: datetime):
    """Fetch weather rows for a UTC-naive window [utc_start, utc_end)."""

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM weather
                WHERE timestamp >= %s AND timestamp < %s
                ORDER BY timestamp
                """,
                (utc_start, utc_end),
            )
            return cursor.fetchall()
    finally:
        conn.close()


def upsert_weather_rows(rows: list[dict], *, city: str = "Alafors") -> int:
    """Upsert weather rows.

    Each row must have keys: timestamp (UTC-naive datetime), temperature, vind, symbol_code.
    Returns total affected rows reported by the driver.
    """

    if not rows:
        return 0

    values = []
    for row in rows:
        values.append(
            (
                city,
                row.get("temperature"),
                row.get("vind"),
                row.get("timestamp"),
                row.get("timestamp"),
                row.get("symbol_code"),
            )
        )

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO weather (city, temperature, vind, timestamp, observation_time, symbol_code)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    city = VALUES(city),
                    temperature = VALUES(temperature),
                    vind = VALUES(vind),
                    observation_time = VALUES(observation_time),
                    symbol_code = VALUES(symbol_code)
                """,
                values,
            )
        conn.commit()
        return int(conn.affected_rows())
    finally:
        conn.close()


def fetch_avg_temperature(utc_start: datetime, utc_end: datetime):
    """Return average temperature for a UTC-naive window or None."""

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT AVG(temperature) AS avgtemp
                FROM weather
                WHERE timestamp >= %s AND timestamp < %s
                """,
                (utc_start, utc_end),
            )
            row = cur.fetchone() or {}
            return row.get("avgtemp")
    finally:
        conn.close()
