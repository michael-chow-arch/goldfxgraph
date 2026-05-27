from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from math import isfinite
from typing import Any

import httpx
from pydantic import ValidationError

from goldfxgraph.market_data.current_quote import QuoteProviderError
from goldfxgraph.schemas.forecast import CurrentQuote

DEFAULT_TRADINGVIEW_URL = "https://www.tradingview.com/symbols/XAUUSD/"
DEFAULT_TRADINGVIEW_SOURCE = "TradingView"

_JSON_LD_BLOCK_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>\s*(?P<body>.*?)\s*</script>',
    re.IGNORECASE | re.DOTALL,
)
_SHORT_NAME_RE = re.compile(r'"short_name"\s*:\s*"(?P<symbol>[^"]+)"')
_TICKER_SYMBOL_RE = re.compile(r'"tickerSymbol"\s*:\s*"(?P<symbol>[^"]+)"')
_TRADE_PRICE_RE = re.compile(r'"trade"\s*:\s*\{\s*"price"\s*:\s*"?(?P<price>[0-9]+(?:\.[0-9]+)?)"?', re.DOTALL)
_DAILY_BAR_PRICE_RE = re.compile(
    r'"daily_bar"\s*:\s*\{(?P<body>.*?)\}\s*[,}]',
    re.DOTALL,
)


class TradingViewQuoteProvider:
    def __init__(
        self,
        url: str = DEFAULT_TRADINGVIEW_URL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.url = url
        self.transport = transport

    def fetch(self) -> CurrentQuote:
        try:
            with httpx.Client(transport=self.transport, timeout=10, follow_redirects=True) as client:
                response = client.get(self.url, headers=self._headers())
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise QuoteProviderError("TradingView quote request failed") from exc

        quote = _quote_from_html(response.text)
        return quote

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (compatible; GoldFXGraph/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }


def _quote_from_html(html: str) -> CurrentQuote:
    symbol = _extract_symbol(html)
    current_price = _extract_current_price(html)
    data_timestamp = _extract_data_timestamp(html)
    data_source = _extract_data_source(html)

    try:
        quote = CurrentQuote(
            symbol=symbol,
            current_price=current_price,
            data_source=data_source,
            data_timestamp=data_timestamp,
        )
    except ValidationError as exc:
        raise QuoteProviderError(f"TradingView quote payload is invalid: {exc.errors()[0]['msg']}") from exc

    if not isfinite(quote.current_price) or quote.current_price <= 0:
        raise QuoteProviderError("TradingView quote payload contains invalid price")
    if not quote.data_source.strip():
        raise QuoteProviderError("TradingView quote payload contains invalid data source")
    return quote


def _extract_symbol(html: str) -> str:
    symbol = _first_match(html, [_SHORT_NAME_RE, _TICKER_SYMBOL_RE])
    if symbol is None:
        raise QuoteProviderError("TradingView quote page missing symbol")
    return symbol.strip().upper()


def _extract_current_price(html: str) -> float:
    price_text = _first_match(html, [_TRADE_PRICE_RE])
    if price_text is None:
        price_text = _extract_from_daily_bar(html, "close")
    if price_text is None:
        price_text = _extract_from_json_ld_price(html)
    if price_text is None:
        raise QuoteProviderError("TradingView quote page missing current price")

    try:
        price = float(price_text)
    except (TypeError, ValueError) as exc:
        raise QuoteProviderError("TradingView quote page contains invalid price") from exc
    if not isfinite(price) or price <= 0:
        raise QuoteProviderError("TradingView quote page contains invalid price")
    return price


def _extract_data_timestamp(html: str) -> datetime:
    timestamp_text = _extract_from_daily_bar(html, "data_update_time")
    if timestamp_text is None:
        timestamp_text = _extract_from_json_ld_timestamp(html)
    if timestamp_text is None:
        raise QuoteProviderError("TradingView quote page missing data timestamp")

    try:
        timestamp = float(timestamp_text)
    except (TypeError, ValueError) as exc:
        parsed = _parse_timestamp_string(timestamp_text)
        if parsed is None:
            raise QuoteProviderError("TradingView quote page contains invalid data timestamp") from exc
        return parsed

    if not isfinite(timestamp):
        raise QuoteProviderError("TradingView quote page contains invalid data timestamp")
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _extract_data_source(html: str) -> str:
    data_source = _extract_from_json_ld_value(html, "provider", "name")
    if data_source is None:
        raise QuoteProviderError("TradingView quote page missing data source")
    normalized = data_source.strip()
    if normalized.lower() != "tradingview":
        raise QuoteProviderError("TradingView quote page returned unexpected data source")
    return DEFAULT_TRADINGVIEW_SOURCE


def _extract_from_json_ld_price(html: str) -> str | None:
    for block in _iter_json_ld_documents(html):
        offers = block.get("offers")
        if isinstance(offers, dict):
            price = offers.get("price")
            if price is not None:
                return str(price)
    return None


def _extract_from_json_ld_timestamp(html: str) -> str | None:
    for block in _iter_json_ld_documents(html):
        offers = block.get("offers")
        if isinstance(offers, dict):
            timestamp = offers.get("priceValidUntil")
            if timestamp is not None:
                return str(timestamp)
    return None


def _extract_from_json_ld_value(html: str, *path: str) -> str | None:
    for block in _iter_json_ld_documents(html):
        value: Any = block
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if isinstance(value, str):
            return value
    return None


def _iter_json_ld_documents(html: str) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for match in _JSON_LD_BLOCK_RE.finditer(html):
        raw_body = match.group("body").strip()
        if not raw_body:
            continue
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            documents.append(parsed)
        elif isinstance(parsed, list):
            documents.extend(item for item in parsed if isinstance(item, dict))
    return documents


def _extract_from_daily_bar(html: str, field_name: str) -> str | None:
    match = _DAILY_BAR_PRICE_RE.search(html)
    if match is None:
        return None

    body = match.group("body")
    field_match = re.search(rf'"{re.escape(field_name)}"\s*:\s*"?(?P<value>[^",}}]+)"?', body)
    if field_match is None:
        return None
    return field_match.group("value")


def _parse_timestamp_string(value: str) -> datetime | None:
    rendered = value.strip()
    if not rendered:
        return None
    if rendered.endswith("Z"):
        rendered = f"{rendered[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(rendered)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _first_match(html: str, patterns: list[re.Pattern[str]]) -> str | None:
    for pattern in patterns:
        match = pattern.search(html)
        if match is not None:
            return match.group(1) if match.groups() else match.group("symbol")
    return None
