from __future__ import annotations

import json
import re
import ssl
import time
import urllib.parse
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from math import isfinite
from typing import Any

import certifi
import httpx
from pydantic import ValidationError
from websockets.sync.client import connect as websocket_connect
from websockets.sync.connection import Connection

from goldfxgraph.market_data.current_quote import QuoteProviderError
from goldfxgraph.persistence.external_source_registry import ExternalSourceSnapshot
from goldfxgraph.schemas.forecast import CurrentQuote

DEFAULT_TRADINGVIEW_LIVE_SYMBOL = "XAUUSD"

_SOCKET_FRAME_RE = re.compile(r"~m~(\d+)~m~")

QuoteSocketFactory = Callable[..., AbstractContextManager[Connection]]


class TradingViewQuoteProvider:
    def __init__(
        self,
        source: ExternalSourceSnapshot,
        transport: httpx.BaseTransport | None = None,
        socket_factory: QuoteSocketFactory | None = None,
    ) -> None:
        self.source = source
        self.transport = transport
        self.socket_factory = socket_factory or _default_socket_factory

    def fetch(self) -> CurrentQuote:
        try:
            current_price, data_timestamp = _fetch_live_quote(
                source=self.source,
                socket_factory=self.socket_factory,
            )
        except QuoteProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise QuoteProviderError("TradingView quote request failed") from exc

        source_name = _require_source_name(self.source)
        try:
            quote = CurrentQuote(
                symbol=DEFAULT_TRADINGVIEW_LIVE_SYMBOL,
                current_price=current_price,
                data_source=source_name,
                data_timestamp=data_timestamp,
            )
        except ValidationError as exc:
            raise QuoteProviderError(f"TradingView quote payload is invalid: {exc.errors()[0]['msg']}") from exc

        if not isfinite(quote.current_price) or quote.current_price <= 0:
            raise QuoteProviderError("TradingView quote payload contains invalid price")
        if not quote.data_source.strip():
            raise QuoteProviderError("TradingView quote payload contains invalid data source")
        return quote


def _fetch_live_quote(
    source: ExternalSourceSnapshot,
    socket_factory: QuoteSocketFactory,
) -> tuple[float, datetime]:
    socket_url = _build_socket_url(source)
    origin = _require_request_config_value(source, "origin")
    user_agent = _require_request_config_value(source, "user_agent")
    referer = source.endpoint_url
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    price: float | None = None
    data_timestamp: datetime | None = None
    received_any_frame = False

    with socket_factory(
        socket_url=socket_url,
        origin=origin,
        referer=referer,
        user_agent=user_agent,
        ssl_context=ssl_context,
    ) as socket:
        session_name = "qs_goldfxgraph"
        _send_socket_message(socket, {"m": "quote_create_session", "p": [session_name]})
        _send_socket_message(
            socket,
            {
                "m": "quote_set_fields",
                "p": [session_name, "lp", "lp_time", "trade_loaded"],
            },
        )
        symbol = _require_request_config_value(source, "symbol")
        _send_socket_message(socket, {"m": "quote_add_symbols", "p": [session_name, symbol]})
        _send_socket_message(socket, {"m": "quote_fast_symbols", "p": [session_name, symbol]})

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                raw_frame = socket.recv(timeout=remaining)
            except TimeoutError as exc:
                if received_any_frame:
                    raise QuoteProviderError("TradingView quote websocket missing live price or timestamp") from exc
                raise QuoteProviderError("TradingView quote websocket timed out") from exc

            received_any_frame = True
            for payload in _iter_socket_payloads(raw_frame):
                parsed = _parse_socket_payload(payload)
                if parsed is None or parsed.get("m") != "qsd":
                    continue

                quote_update = _extract_quote_update(parsed)
                if quote_update is None:
                    continue

                update_price, update_timestamp = quote_update
                if update_price is not None:
                    price = update_price
                if update_timestamp is not None:
                    data_timestamp = update_timestamp
                if price is not None and data_timestamp is not None:
                    return price, data_timestamp

        raise QuoteProviderError("TradingView quote websocket missing live price or timestamp")


def _require_request_config_value(source: ExternalSourceSnapshot, key: str) -> str:
    value = source.request_config.get(key)
    rendered = str(value or "").strip()
    if not rendered:
        raise QuoteProviderError(f"TradingView quote source is missing required config: {key}")
    return rendered


def _require_source_name(source: ExternalSourceSnapshot) -> str:
    source_name = source.request_config.get("source_name")
    rendered = str(source_name or "").strip()
    return rendered or "TradingView"


def _build_socket_url(source: ExternalSourceSnapshot) -> str:
    base_url = _require_request_config_value(source, "socket_url")
    socket_from = str(source.request_config.get("socket_from") or "").strip()
    if not socket_from:
        raise QuoteProviderError("TradingView quote source is missing required config: socket_from")
    auth = str(source.request_config.get("auth") or "").strip()
    if not auth:
        raise QuoteProviderError("TradingView quote source is missing required config: auth")
    query = urllib.parse.urlencode(
        {
            "from": socket_from,
            "date": datetime.now(UTC).isoformat(timespec="seconds"),
            "auth": auth,
        }
    )
    return f"{base_url}?{query}"


def _default_socket_factory(
    *,
    socket_url: str,
    origin: str,
    referer: str,
    user_agent: str,
    ssl_context: ssl.SSLContext,
) -> AbstractContextManager[Connection]:
    return websocket_connect(
        socket_url,
        origin=origin,
        additional_headers={"Referer": referer},
        user_agent_header=user_agent,
        ssl=ssl_context,
        ping_interval=None,
        open_timeout=10,
        close_timeout=10,
        proxy=None,
    )


def _send_socket_message(socket: Any, message: dict[str, Any]) -> None:
    payload = json.dumps(message, separators=(",", ":"))
    socket.send(f"~m~{len(payload)}~m~{payload}")


def _iter_socket_payloads(raw_frame: str | bytes) -> Iterator[str]:
    if isinstance(raw_frame, bytes):
        raw_text = raw_frame.decode("utf-8", errors="ignore")
    else:
        raw_text = raw_frame

    cursor = 0
    while cursor < len(raw_text):
        match = _SOCKET_FRAME_RE.search(raw_text, cursor)
        if match is None:
            return

        payload_length = int(match.group(1))
        payload_start = match.end()
        payload_end = payload_start + payload_length
        if payload_end > len(raw_text):
            return

        yield raw_text[payload_start:payload_end]
        cursor = payload_end


def _parse_socket_payload(payload: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def _extract_quote_update(parsed: dict[str, Any]) -> tuple[float | None, datetime | None] | None:
    params = parsed.get("p")
    if not isinstance(params, list) or len(params) < 2:
        return None

    symbol_payload = params[1]
    if not isinstance(symbol_payload, dict):
        return None

    values = symbol_payload.get("v")
    if not isinstance(values, dict):
        return None

    price = _coerce_float(values.get("lp"))
    timestamp = _coerce_timestamp(values.get("lp_time"))

    if price is None and timestamp is None:
        return None
    return price, timestamp


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(price) or price <= 0:
        return None
    return price


def _coerce_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None

    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(timestamp):
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)
