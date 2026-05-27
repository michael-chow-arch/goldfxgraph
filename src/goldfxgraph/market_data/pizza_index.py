from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass
from statistics import mean
from typing import Any

import httpx

PIZZINT_URL = "https://www.pizzint.watch/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class PizzaIndexError(RuntimeError):
    """Pentagon pizza index 页面不可用或无法解析。"""


@dataclass(frozen=True)
class PizzaLocation:
    place_id: str
    name: str
    spike_pct: int
    distance_mi: float | None = None


def fetch_pizza_index(
    transport: httpx.BaseTransport | None = None,
    *,
    url: str = PIZZINT_URL,
) -> dict[str, Any]:
    with httpx.Client(
        transport=transport,
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        response = client.get(url)
        response.raise_for_status()

    html = response.text
    doughcon = _parse_doughcon(html)
    locations = _parse_locations(html)
    if not doughcon and not locations:
        raise PizzaIndexError("pizza index dashboard did not expose a usable snapshot")

    locations = sorted(locations, key=lambda item: item.spike_pct, reverse=True)
    source_count = len(locations)
    average_spike_pct = round(mean(location.spike_pct for location in locations), 2) if locations else None
    max_spike_pct = max((location.spike_pct for location in locations), default=None)
    pizza_index_score = _score_from_snapshot(doughcon, average_spike_pct, max_spike_pct)
    activity_bias = _activity_bias_from_score(pizza_index_score)
    top_locations = [
        {
            "place_id": location.place_id,
            "name": location.name,
            "spike_pct": location.spike_pct,
            "distance_mi": location.distance_mi,
        }
        for location in locations[:5]
    ]

    avg_display = f"{average_spike_pct:.0f}%" if average_spike_pct is not None else "未知"
    max_display = f"{max_spike_pct:.0f}%" if max_spike_pct is not None else "未知"

    top_location_name = locations[0].name if locations else "unknown"
    top_location_spike = max_display if locations else "未知"

    if doughcon:
        summary = (
            f"Pentagon Pizza Index 当前为 DOUGHCON {doughcon['level']}（"
            f"{doughcon['label']} / {doughcon['description']}），"
            f"从 {source_count} 家门店监测到平均 {avg_display} 的活跃度，"
            f"最高 {top_location_name} 达到 {top_location_spike} 的 SPIKE，指数分 {pizza_index_score}/100，"
            f"整体偏 {activity_bias}。"
        )
    else:
        summary = (
            f"Pentagon Pizza Index 已抓取到 {source_count} 家门店的活动数据，"
            f"平均活跃度 {avg_display}，最高 {top_location_name} 达到 {top_location_spike} 的 SPIKE，"
            f"指数分 {pizza_index_score}/100，整体偏 {activity_bias}。"
        )

    return {
        "status": "available",
        "source": "pizzint.watch",
        "url": url,
        "doughcon_level": doughcon["level"] if doughcon else None,
        "doughcon_label": doughcon["label"] if doughcon else None,
        "doughcon_description": doughcon["description"] if doughcon else None,
        "source_count": source_count,
        "average_spike_pct": average_spike_pct,
        "max_spike_pct": max_spike_pct,
        "pizza_index_score": pizza_index_score,
        "activity_bias": activity_bias,
        "top_locations": top_locations,
        "summary": summary,
    }


def _parse_doughcon(html_text: str) -> dict[str, Any] | None:
    match = re.search(
        (
            r"DOUGHCON\s+(\d+).*?<span>([^<]+)</span>.*?"
            r"<span[^>]*>\s*•\s*</span>.*?<span>([^<]+)</span>"
        ),
        html_text,
        re.S,
    )
    if not match:
        return None
    return {
        "level": int(match.group(1)),
        "label": _clean_text(match.group(2)),
        "description": _clean_text(match.group(3)),
    }


def _parse_locations(html_text: str) -> list[PizzaLocation]:
    pattern = re.compile(
        (
            r'<div data-place-id=[\'"]([^\'"]+)[\'"][^>]*>.*?<h3[^>]*>(.*?)</h3>.*?'
            r"<span[^>]*>(\d+)<!-- -->% SPIKE</span>.*?<div[^>]*>([^<]+)</div>"
        ),
        re.S,
    )
    locations: list[PizzaLocation] = []
    for match in pattern.finditer(html_text):
        place_id = _clean_text(match.group(1))
        name = html_lib.unescape(_clean_text(match.group(2)))
        spike_pct = int(match.group(3))
        distance_mi = _parse_distance(match.group(4))
        locations.append(
            PizzaLocation(
                place_id=place_id,
                name=name,
                spike_pct=spike_pct,
                distance_mi=distance_mi,
            )
        )
    return locations


def _parse_distance(value: str) -> float | None:
    cleaned = _clean_text(value).replace("mi", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _score_from_snapshot(
    doughcon: dict[str, Any] | None,
    average_spike_pct: float | None,
    max_spike_pct: int | None,
) -> int:
    score = 0.0
    if average_spike_pct is not None:
        score += max(0.0, (average_spike_pct - 100.0) * 0.5)
    if max_spike_pct is not None:
        score += max(0.0, (float(max_spike_pct) - 100.0) * 0.25)
    if doughcon is not None:
        score += (doughcon["level"] - 1) * 12.0
    return int(min(100, round(score)))


def _activity_bias_from_score(score: int) -> str:
    if score >= 70:
        return "bullish"
    if score <= 30:
        return "neutral"
    return "watch"


def _clean_text(value: str | None) -> str:
    return (value or "").strip()
