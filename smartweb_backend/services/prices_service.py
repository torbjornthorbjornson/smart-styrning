from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from smartweb_backend.db.prices_repo import fetch_electricity_prices
from smartweb_backend.time_utils import local_day_to_utc_window, utc_naive_to_local_label


@dataclass(frozen=True)
class DailyPriceView:
    day_local: date
    top_n: int
    no_price: bool
    labels: list[str]
    values: list[float]
    threshold: float
    selected_labels_chrono: list[str]
    sorted_by_price: list[dict[str, Any]]
    bar_colors: list[str]


def fetch_prices_for_local_day(day_local: date):
    utc_start, utc_end = local_day_to_utc_window(day_local)
    return fetch_electricity_prices(utc_start, utc_end)


def build_daily_price_view(day_local: date, top_n: int) -> DailyPriceView:
    rows = fetch_prices_for_local_day(day_local)
    if not rows:
        return DailyPriceView(
            day_local=day_local,
            top_n=max(int(top_n), 1),
            no_price=True,
            labels=[],
            values=[],
            threshold=0.0,
            selected_labels_chrono=[],
            sorted_by_price=[],
            bar_colors=[],
        )

    labels = [utc_naive_to_local_label(r["datetime"]) for r in rows if r.get("price") is not None]
    values = [float(r["price"]) for r in rows if r.get("price") is not None]

    pairs = [(values[i], i) for i in range(len(values))]
    pairs.sort(key=lambda t: (t[0], t[1]))

    N = min(max(int(top_n), 1), len(pairs))
    chosen = pairs[:N]
    selected_idx = [i for _, i in chosen]
    selected_set = set(selected_idx)

    threshold = max((values[i] for i in selected_idx), default=0.0)
    selected_labels_chrono = [labels[i] for i in sorted(selected_idx)]
    sorted_by_price = [{"label": labels[i], "price": values[i]} for (p, i) in pairs]

    bar_colors = ["green" if i in selected_set else "blue" for i in range(len(values))]

    return DailyPriceView(
        day_local=day_local,
        top_n=N,
        no_price=False,
        labels=labels,
        values=values,
        threshold=threshold,
        selected_labels_chrono=selected_labels_chrono,
        sorted_by_price=sorted_by_price,
        bar_colors=bar_colors,
    )
