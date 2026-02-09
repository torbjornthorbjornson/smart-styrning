from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from smartweb_backend.db.prices_repo import fetch_electricity_prices
from smartweb_backend.db.weather_repo import fetch_weather
from smartweb_backend.time_utils import local_day_to_utc_window, utc_naive_to_local_label


@dataclass(frozen=True)
class ElprisVaderView:
    day_local: date
    weather_data: list[dict]
    elpris_data: list[dict]
    labels: list[str]
    temperature: list[float]
    vind: list[float]
    elpris_labels: list[str]
    elpris_values: list[float]
    medel_temperature: str | float
    medel_vind: str | float
    medel_elpris: str | float


def build_elpris_vader_view(day_local: date) -> ElprisVaderView:
    utc_start, utc_end = local_day_to_utc_window(day_local)

    weather_data = fetch_weather(utc_start, utc_end)
    elpris_data = fetch_electricity_prices(utc_start, utc_end) or []

    medel_temperature = (
        round(sum(row["temperature"] for row in weather_data) / len(weather_data), 1)
        if weather_data
        else "-"
    )
    medel_vind = (
        round(sum(row["vind"] for row in weather_data) / len(weather_data), 1) if weather_data else "-"
    )
    medel_elpris = (
        round(sum(row["price"] for row in elpris_data) / len(elpris_data), 1) if elpris_data else "-"
    )

    labels = [utc_naive_to_local_label(row["timestamp"]) for row in weather_data]
    temperature = [row["temperature"] for row in weather_data]
    vind = [row["vind"] for row in weather_data]

    elpris_labels = [utc_naive_to_local_label(row["datetime"]) for row in elpris_data]
    elpris_values = [row["price"] for row in elpris_data]

    return ElprisVaderView(
        day_local=day_local,
        weather_data=weather_data,
        elpris_data=elpris_data,
        labels=labels,
        temperature=temperature,
        vind=vind,
        elpris_labels=elpris_labels,
        elpris_values=elpris_values,
        medel_temperature=medel_temperature,
        medel_vind=medel_vind,
        medel_elpris=medel_elpris,
    )
