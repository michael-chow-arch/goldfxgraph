from __future__ import annotations

import json
import secrets
import ssl
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from math import isfinite
from typing import Any
from urllib.parse import quote

import certifi
import httpx
from pydantic import ValidationError
from websockets.sync.client import connect

from goldfxgraph.schemas.forecast import DailyBar

TRADINGVIEW_HISTORY_HTTP_URL = "https://www.tradingview.com/history"
TRADINGVIEW_CHART_WS_URL = "wss://data.tradingview.com/socket.io/websocket"
TRADINGVIEW_HISTORY_SOURCE = "TradingView"
TRADINGVIEW_GOLD_SYMBOL = "XAUUSD"
TRADINGVIEW_CHART_SYMBOL = "OANDA:XAUUSD"
TRADINGVIEW_CHART_TIMEZONE = "Etc/UTC"
TRADINGVIEW_CHART_ORIGIN = "https://www.tradingview.com"
TRADINGVIEW_CHART_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) GoldFXGraph/1.0"
TRADINGVIEW_AUTH_TOKEN = "unauthorized_user_token"
TRADINGVIEW_CHART_SERIES_ID = "s1"
TRADINGVIEW_CHART_SYMBOL_ALIAS = "symbol_1"


class TradingViewHistoryError(RuntimeError):
    """TradingView 历史日线拉取或解析失败。"""


def fetch_gold_daily_bars(
    *,
    start_date: date,
    end_date: date,
    transport: httpx.BaseTransport | None = None,
) -> list[DailyBar]:
    if start_date > end_date:
        return []

    if transport is not None:
        return _fetch_gold_daily_bars_via_http_mock(
            start_date=start_date,
            end_date=end_date,
            transport=transport,
        )

    return _fetch_gold_daily_bars_via_chart_websocket(start_date=start_date, end_date=end_date)


def _fetch_gold_daily_bars_via_http_mock(
    *,
    start_date: date,
    end_date: date,
    transport: httpx.BaseTransport,
) -> list[DailyBar]:
    period1 = int(datetime.combine(start_date, time.min, tzinfo=UTC).timestamp())
    period2 = int(datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC).timestamp())
    params = {
        "symbol": TRADINGVIEW_GOLD_SYMBOL,
        "resolution": "D",
        "from": period1,
        "to": period2,
    }
    headers = {"User-Agent": TRADINGVIEW_CHART_USER_AGENT, "Accept": "application/json"}

    try:
        with httpx.Client(transport=transport, timeout=20) as client:
            response = client.get(TRADINGVIEW_HISTORY_HTTP_URL, params=params, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise TradingViewHistoryError("TradingView history request failed") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise TradingViewHistoryError("TradingView history payload is invalid") from exc

    bars = _parse_http_history_payload(payload, start_date=start_date, end_date=end_date)
    bars.sort(key=lambda bar: bar.date)
    return bars


def _fetch_gold_daily_bars_via_chart_websocket(*, start_date: date, end_date: date) -> list[DailyBar]:
    requested_count = _requested_bar_count(start_date=start_date, end_date=end_date)
    session_id = _random_session_id("cs_")
    ws_url = _build_chart_ws_url()

    ssl_context = ssl.create_default_context(cafile=certifi.where())
    bars_by_date: dict[date, DailyBar] = {}
    series_completed = False

    try:
        with connect(
            ws_url,
            origin=TRADINGVIEW_CHART_ORIGIN,
            user_agent_header=TRADINGVIEW_CHART_USER_AGENT,
            ssl=ssl_context,
            open_timeout=15,
            ping_interval=20,
            ping_timeout=20,
            max_size=20 * 1024 * 1024,
        ) as ws:
            _send_chart_message(ws, "set_auth_token", [TRADINGVIEW_AUTH_TOKEN])
            _send_chart_message(ws, "chart_create_session", [session_id, ""])
            _send_chart_message(
                ws,
                "resolve_symbol",
                [session_id, TRADINGVIEW_CHART_SYMBOL_ALIAS, _resolve_symbol_payload()],
            )
            _send_chart_message(
                ws,
                "create_series",
                [
                    session_id,
                    TRADINGVIEW_CHART_SERIES_ID,
                    TRADINGVIEW_CHART_SERIES_ID,
                    TRADINGVIEW_CHART_SYMBOL_ALIAS,
                    "D",
                    requested_count,
                ],
            )
            _send_chart_message(ws, "switch_timezone", [session_id, TRADINGVIEW_CHART_TIMEZONE])

            while True:
                try:
                    raw_message = ws.recv(timeout=5)
                except TimeoutError:
                    break

                for message_kind, payload in _split_chart_frames(raw_message):
                    if message_kind == "heartbeat":
                        _send_heartbeat(ws, payload)
                        continue

                    message = _decode_chart_message(payload)
                    if message.get("m") == "timescale_update":
                        for bar in _extract_daily_bars_from_timescale_update(
                            message,
                            start_date=start_date,
                            end_date=end_date,
                        ):
                            existing_bar = bars_by_date.get(bar.date)
                            if existing_bar is not None and existing_bar.model_dump() != bar.model_dump():
                                raise TradingViewHistoryError(
                                    f"TradingView returned conflicting daily bars for {bar.date.isoformat()}"
                                )
                            bars_by_date[bar.date] = bar
                    elif message.get("m") == "series_completed":
                        params = message.get("p")
                        if (
                            isinstance(params, list)
                            and len(params) >= 2
                            and params[0] == session_id
                            and params[1] == TRADINGVIEW_CHART_SERIES_ID
                        ):
                            series_completed = True
                            break
                    if message.get("m") == "protocol_error":
                        raise TradingViewHistoryError("TradingView chart session returned protocol_error")
                if series_completed:
                    break
    except TradingViewHistoryError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise TradingViewHistoryError("TradingView chart websocket request failed") from exc

    if not series_completed:
        raise TradingViewHistoryError("TradingView chart websocket timed out before series completion")

    bars = sorted(bars_by_date.values(), key=lambda bar: bar.date)
    if not bars:
        raise TradingViewHistoryError("TradingView history payload missing bar data")
    return bars


def _build_chart_ws_url() -> str:
    session_suffix = datetime.now(UTC).strftime("%Y_%m_%d-%H_%M")
    return f"{TRADINGVIEW_CHART_WS_URL}?from={quote('chart/goldfxgraph/', safe='')}&date={session_suffix}"


def _requested_bar_count(*, start_date: date, end_date: date) -> int:
    span_days = (end_date - start_date).days + 1
    return max(50, min(1000, span_days * 8 + 50))


def _resolve_symbol_payload() -> str:
    return '={"symbol":"OANDA:XAUUSD","adjustment":"splits"}'


def _random_session_id(prefix: str) -> str:
    return f"{prefix}{secrets.token_hex(8)}"


def _send_chart_message(ws: Any, method: str, params: list[Any]) -> None:
    payload = json.dumps({"m": method, "p": params}, separators=(",", ":"))
    ws.send(f"~m~{len(payload)}~m~{payload}")


def _send_heartbeat(ws: Any, payload: str) -> None:
    try:
        ws.send(f"~h~{int(payload)}")
    except ValueError:
        return


def _split_chart_frames(raw_message: Any) -> list[tuple[str, str]]:
    if isinstance(raw_message, bytes):
        data = raw_message.decode("utf-8", errors="replace")
    else:
        data = str(raw_message)

    frames: list[tuple[str, str]] = []
    cursor = 0
    while cursor < len(data):
        if data.startswith("~h~", cursor):
            heartbeat_end = data.find("~h~", cursor + 3)
            if heartbeat_end == -1:
                break
            frames.append(("heartbeat", data[cursor + 3 : heartbeat_end]))
            cursor = heartbeat_end + 3
            continue

        if not data.startswith("~m~", cursor):
            break

        length_end = data.find("~m~", cursor + 3)
        if length_end == -1:
            break

        try:
            length = int(data[cursor + 3 : length_end])
        except ValueError:
            break

        body_start = length_end + 3
        body_end = body_start + length
        if body_end > len(data):
            break

        frames.append(("message", data[body_start:body_end]))
        cursor = body_end

    return frames


def _decode_chart_message(payload: str) -> dict[str, Any]:
    try:
        message = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise TradingViewHistoryError("TradingView chart payload is invalid") from exc

    if not isinstance(message, dict):
        raise TradingViewHistoryError("TradingView chart payload is invalid")

    if "m" in message and "p" in message:
        message.setdefault("method", message["m"])
        message.setdefault("params", message["p"])
        message.setdefault("time", message.get("t"))
    return message


def _extract_daily_bars_from_timescale_update(
    message: dict[str, Any],
    *,
    start_date: date,
    end_date: date,
) -> list[DailyBar]:
    params = message.get("p")
    if not isinstance(params, list) or len(params) < 2:
        raise TradingViewHistoryError("TradingView timescale_update payload missing series data")

    series_payload = params[1]
    if not isinstance(series_payload, dict):
        raise TradingViewHistoryError("TradingView timescale_update payload missing series data")

    candidates_by_date: dict[date, list[DailyBar]] = defaultdict(list)
    for series_data in series_payload.values():
        if not isinstance(series_data, dict):
            continue
        rows = series_data.get("s")
        if not isinstance(rows, list):
            continue
        for row in rows:
            bar = _build_daily_bar_from_series_row(row, start_date=start_date, end_date=end_date)
            if bar is None:
                continue
            candidates_by_date[bar.date].append(bar)

    bars: list[DailyBar] = []
    for _bar_date, candidates in candidates_by_date.items():
        if len(candidates) == 1:
            bars.append(candidates[0])
            continue

        first_payload = candidates[0].model_dump()
        if all(candidate.model_dump() == first_payload for candidate in candidates[1:]):
            bars.append(candidates[0])
            continue

        raise TradingViewHistoryError(
            f"TradingView returned conflicting daily bars for {candidates[0].date.isoformat()}"
        )

    bars.sort(key=lambda bar: bar.date)
    return bars


def _build_daily_bar_from_series_row(
    row: Any,
    *,
    start_date: date,
    end_date: date,
) -> DailyBar | None:
    if not isinstance(row, dict):
        return None

    values = row.get("v")
    if not isinstance(values, list) or len(values) < 5:
        return None

    timestamp = _coerce_timestamp(values[0])
    if timestamp is None:
        return None

    bar_time = datetime.fromtimestamp(timestamp, tz=UTC)
    bar_date = bar_time.date()
    if bar_date < start_date or bar_date > end_date:
        return None
    open_price = _coerce_price(values[1] if len(values) > 1 else None)
    high_price = _coerce_price(values[2] if len(values) > 2 else None)
    low_price = _coerce_price(values[3] if len(values) > 3 else None)
    close_price = _coerce_price(values[4] if len(values) > 4 else None)
    volume = _coerce_volume(values[5] if len(values) > 5 else None)

    if open_price is None or high_price is None or low_price is None or close_price is None:
        return None

    try:
        return DailyBar(
            date=bar_date,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            source=TRADINGVIEW_HISTORY_SOURCE,
            symbol=TRADINGVIEW_GOLD_SYMBOL,
        )
    except ValidationError:
        return None


def _parse_http_history_payload(payload: Any, *, start_date: date, end_date: date) -> list[DailyBar]:
    if not isinstance(payload, dict):
        raise TradingViewHistoryError("TradingView history payload is invalid")

    status = payload.get("s")
    if status == "no_data":
        return []
    if status not in {None, "ok"}:
        raise TradingViewHistoryError("TradingView history payload returned an unexpected status")

    rows = _extract_http_rows(payload)
    candidates_by_date: dict[date, list[DailyBar]] = defaultdict(list)
    for row in rows:
        bar = _build_daily_bar_from_http_row(row, start_date=start_date, end_date=end_date)
        if bar is None:
            continue
        candidates_by_date[bar.date].append(bar)

    bars: list[DailyBar] = []
    for _bar_date, candidates in candidates_by_date.items():
        if len(candidates) == 1:
            bars.append(candidates[0])
            continue

        first_payload = candidates[0].model_dump()
        if all(candidate.model_dump() == first_payload for candidate in candidates[1:]):
            bars.append(candidates[0])
            continue

        raise TradingViewHistoryError(
            f"TradingView returned conflicting daily bars for {candidates[0].date.isoformat()}"
        )

    return bars


def _extract_http_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if all(key in payload for key in ("t", "o", "h", "l", "c")):
        timestamps = payload.get("t")
        if not isinstance(timestamps, list):
            raise TradingViewHistoryError("TradingView history payload missing timestamps")
        return [
            {
                "time": timestamp,
                "open": payload.get("o", []),
                "high": payload.get("h", []),
                "low": payload.get("l", []),
                "close": payload.get("c", []),
                "volume": payload.get("v", []),
                "index": index,
            }
            for index, timestamp in enumerate(timestamps)
        ]

    rows = payload.get("bars")
    if isinstance(rows, list):
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                normalized_rows.append(row)
        return normalized_rows

    raise TradingViewHistoryError("TradingView history payload missing bar data")


def _build_daily_bar_from_http_row(
    row: dict[str, Any],
    *,
    start_date: date,
    end_date: date,
) -> DailyBar | None:
    timestamp = row.get("time")
    if not isinstance(timestamp, (int, float)):
        return None

    bar_time = datetime.fromtimestamp(int(timestamp), tz=UTC)
    if bar_time.time() != time.min:
        return None

    bar_date = bar_time.date()
    if bar_date < start_date or bar_date > end_date:
        return None
    if "index" in row:
        index = row["index"]
        open_price = _coerce_price(_pick_list_value(row.get("open"), index))
        high_price = _coerce_price(_pick_list_value(row.get("high"), index))
        low_price = _coerce_price(_pick_list_value(row.get("low"), index))
        close_price = _coerce_price(_pick_list_value(row.get("close"), index))
        volume = _coerce_volume(_pick_list_value(row.get("volume"), index))
    else:
        open_price = _coerce_price(row.get("open"))
        high_price = _coerce_price(row.get("high"))
        low_price = _coerce_price(row.get("low"))
        close_price = _coerce_price(row.get("close"))
        volume = _coerce_volume(row.get("volume"))

    if open_price is None or high_price is None or low_price is None or close_price is None:
        return None

    try:
        return DailyBar(
            date=bar_date,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            source=TRADINGVIEW_HISTORY_SOURCE,
            symbol=TRADINGVIEW_GOLD_SYMBOL,
        )
    except ValidationError:
        return None


def _pick_list_value(values: Any, index: int) -> Any:
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def _coerce_timestamp(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    return parsed


def _coerce_price(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0 or not isfinite(parsed):
        return None
    return parsed


def _coerce_volume(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0 or not isfinite(parsed):
        return None
    return parsed
