from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UtfallsPlans:
    heat_plan_96: list[int]
    vv_plan_96: list[int]
    heat_plan_24: list[int]
    vv_plan_24: list[int]
    heat_ones: int
    vv_ones: int


def aggregate_plans(heat_plan_96: list[int], vv_plan_96: list[int]) -> UtfallsPlans:
    heat_plan_96 = list(heat_plan_96 or [])
    vv_plan_96 = list(vv_plan_96 or [])

    if len(heat_plan_96) != 96:
        heat_plan_96 = (heat_plan_96 + [0] * 96)[:96]
    if len(vv_plan_96) != 96:
        vv_plan_96 = (vv_plan_96 + [0] * 96)[:96]

    heat_ones = sum(heat_plan_96)
    vv_ones = sum(vv_plan_96)

    heat_plan_24 = [1 if sum(heat_plan_96[h * 4 : (h + 1) * 4]) > 0 else 0 for h in range(24)]
    vv_plan_24 = [1 if sum(vv_plan_96[h * 4 : (h + 1) * 4]) > 0 else 0 for h in range(24)]

    return UtfallsPlans(
        heat_plan_96=heat_plan_96,
        vv_plan_96=vv_plan_96,
        heat_plan_24=heat_plan_24,
        vv_plan_24=vv_plan_24,
        heat_ones=heat_ones,
        vv_ones=vv_ones,
    )


def build_utfall_bar_colors(values_len: int, plans: UtfallsPlans) -> list[str]:
    """Färga staplar efter utfallsplan (4 lägen)."""
    if values_len == 96:
        out: list[str] = []
        for i in range(96):
            h = 1 if plans.heat_plan_96[i] == 1 else 0
            v = 1 if plans.vv_plan_96[i] == 1 else 0
            if h and v:
                out.append("purple")
            elif h:
                out.append("green")
            elif v:
                out.append("orange")
            else:
                out.append("blue")
        return out

    if values_len == 24:
        out = []
        for i in range(24):
            h = 1 if plans.heat_plan_24[i] == 1 else 0
            v = 1 if plans.vv_plan_24[i] == 1 else 0
            if h and v:
                out.append("purple")
            elif h:
                out.append("green")
            elif v:
                out.append("orange")
            else:
                out.append("blue")
        return out

    return ["blue"] * int(values_len)
