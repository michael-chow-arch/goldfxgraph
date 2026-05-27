from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime
from math import isfinite
from typing import Any

import httpx

FRED_DOLLAR_INDEX_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS"
FRED_REAL_RATES_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10"
CFTC_GOLD_COMMITMENTS_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.csv"

CFTC_GOLD_COMMITMENTS_PARAMS: dict[str, str] = {
    "$select": (
        "report_date_as_yyyy_mm_dd,commodity_name,open_interest_all,"
        "noncomm_positions_long_all,noncomm_positions_short_all,"
        "comm_positions_long_all,comm_positions_short_all"
    ),
    "$where": "upper(commodity_name) like '%GOLD%'",
    "$order": "report_date_as_yyyy_mm_dd DESC",
    "$limit": "2",
}


class ExternalSignalError(RuntimeError):
    """外部信号源返回了无效数据或请求失败。"""


def fetch_dollar_index(transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    return _fetch_fred_series(
        transport=transport,
        url=FRED_DOLLAR_INDEX_URL,
        series_id="DTWEXBGS",
        series_name="美元指数",
        unit="index",
    )


def fetch_real_rates(transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    return _fetch_fred_series(
        transport=transport,
        url=FRED_REAL_RATES_URL,
        series_id="DFII10",
        series_name="实际利率",
        unit="percent",
        change_unit="percentage_point",
    )


def fetch_cftc_gold_commitments(transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    with httpx.Client(transport=transport, timeout=20) as client:
        response = client.get(CFTC_GOLD_COMMITMENTS_URL, params=CFTC_GOLD_COMMITMENTS_PARAMS)
        response.raise_for_status()

    rows = _csv_rows(response.text)
    if not rows:
        raise ExternalSignalError("CFTC gold commitments response is empty")

    latest = rows[0]
    previous = rows[1] if len(rows) > 1 else None

    report_date = _parse_date(latest.get("report_date_as_yyyy_mm_dd"))
    commodity_name = str(latest.get("commodity_name") or "GOLD").strip().upper()
    open_interest = _parse_int(latest.get("open_interest_all"), field_name="open_interest_all")
    long_positions = _parse_int(latest.get("noncomm_positions_long_all"), field_name="noncomm_positions_long_all")
    short_positions = _parse_int(latest.get("noncomm_positions_short_all"), field_name="noncomm_positions_short_all")
    comm_long_positions = _parse_int(latest.get("comm_positions_long_all"), field_name="comm_positions_long_all")
    comm_short_positions = _parse_int(latest.get("comm_positions_short_all"), field_name="comm_positions_short_all")

    previous_net_noncommercial = None
    if previous is not None:
        previous_long = _parse_int(previous.get("noncomm_positions_long_all"), field_name="noncomm_positions_long_all")
        previous_short = _parse_int(
            previous.get("noncomm_positions_short_all"),
            field_name="noncomm_positions_short_all",
        )
        previous_net_noncommercial = previous_long - previous_short

    net_noncommercial = long_positions - short_positions
    net_change = None if previous_net_noncommercial is None else net_noncommercial - previous_net_noncommercial
    positioning_bias = _direction_from_net_noncommercial(net_noncommercial)
    positioning_ratio = None if open_interest <= 0 else round(net_noncommercial / open_interest, 4)

    return {
        "status": "available",
        "source": "publicreporting.cftc.gov",
        "series_id": "CFTC_GOLD_COMMITMENTS",
        "series_name": "CFTC 黄金持仓",
        "commodity_name": commodity_name,
        "report_date": report_date.isoformat(),
        "open_interest_all": open_interest,
        "noncomm_positions_long_all": long_positions,
        "noncomm_positions_short_all": short_positions,
        "comm_positions_long_all": comm_long_positions,
        "comm_positions_short_all": comm_short_positions,
        "net_noncommercial": net_noncommercial,
        "previous_net_noncommercial": previous_net_noncommercial,
        "net_change": net_change,
        "positioning_ratio": positioning_ratio,
        "positioning_bias": positioning_bias,
    }


def _fetch_fred_series(
    *,
    transport: httpx.BaseTransport | None,
    url: str,
    series_id: str,
    series_name: str,
    unit: str,
    change_unit: str | None = None,
) -> dict[str, Any]:
    with httpx.Client(transport=transport, timeout=20) as client:
        response = client.get(url)
        response.raise_for_status()

    rows = _csv_rows(response.text)
    if not rows:
        raise ExternalSignalError(f"{series_name} response is empty")

    latest = _first_row_with_value(rows, series_id)
    if latest is None:
        raise ExternalSignalError(f"{series_name} response missing latest observation")

    previous = _previous_row_with_value(rows, series_id, latest)

    observation_date = _parse_date(latest.get("observation_date"))
    value = _parse_float(latest.get(series_id), field_name=series_id)
    previous_value = None
    change = None
    if previous is not None:
        previous_value = _parse_float(previous.get(series_id), field_name=series_id)
        change = value - previous_value

    return {
        "status": "available",
        "source": "fred.stlouisfed.org",
        "series_id": series_id,
        "series_name": series_name,
        "observation_date": observation_date.isoformat(),
        "value": value,
        "previous_value": previous_value,
        "change": change,
        "change_unit": change_unit or unit,
        "unit": unit,
        "direction": _direction_from_change(change),
    }


def _csv_rows(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text.strip()))
    return [dict(row) for row in reader]


def _first_row_with_value(rows: list[dict[str, str]], field_name: str) -> dict[str, str] | None:
    for row in reversed(rows):
        value = row.get(field_name)
        if value is not None and str(value).strip() != "":
            return row
    return None


def _previous_row_with_value(
    rows: list[dict[str, str]],
    field_name: str,
    latest_row: dict[str, str],
) -> dict[str, str] | None:
    latest_index = rows.index(latest_row)
    for row in reversed(rows[:latest_index]):
        value = row.get(field_name)
        if value is not None and str(value).strip() != "":
            return row
    return None


def _parse_date(value: Any) -> date:
    rendered = str(value or "").strip()
    if not rendered:
        raise ExternalSignalError("external signal response missing date")
    if rendered.endswith("Z"):
        rendered = f"{rendered[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(rendered)
    except ValueError:
        try:
            parsed = datetime.strptime(rendered, "%Y-%m-%d")
        except ValueError as inner_exc:
            raise ExternalSignalError(f"invalid external signal date: {rendered}") from inner_exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC)
    return parsed.date()


def _parse_float(value: Any, *, field_name: str) -> float:
    rendered = str(value or "").strip().replace(",", "")
    if not rendered:
        raise ExternalSignalError(f"external signal response missing {field_name}")
    try:
        parsed = float(rendered)
    except ValueError as exc:
        raise ExternalSignalError(f"invalid numeric value for {field_name}") from exc
    if not isfinite(parsed):
        raise ExternalSignalError(f"invalid numeric value for {field_name}")
    return parsed


def _parse_int(value: Any, *, field_name: str) -> int:
    rendered = str(value or "").strip().replace(",", "")
    if not rendered:
        raise ExternalSignalError(f"external signal response missing {field_name}")
    try:
        return int(float(rendered))
    except ValueError as exc:
        raise ExternalSignalError(f"invalid integer value for {field_name}") from exc


def _direction_from_change(change: float | None) -> str:
    if change is None or change == 0:
        return "flat"
    return "up" if change > 0 else "down"


def _direction_from_net_noncommercial(net_noncommercial: int) -> str:
    if net_noncommercial > 0:
        return "bullish"
    if net_noncommercial < 0:
        return "bearish"
    return "neutral"
