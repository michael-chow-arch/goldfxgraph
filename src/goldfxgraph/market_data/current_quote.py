from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from goldfxgraph.schemas.forecast import CurrentQuote


class QuoteProviderError(RuntimeError):
    """当前报价 provider 未配置或返回无效数据。"""


class CurrentQuoteProvider:
    def __init__(self, url: str | None, api_key: str | None, source_name: str | None = None) -> None:
        self.url = url
        self.api_key = api_key
        self.source_name = source_name

    def fetch(self) -> CurrentQuote:
        if not self.url:
            raise QuoteProviderError("Current quote provider is not configured")

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else None
        try:
            response = httpx.get(self.url, headers=headers, timeout=10)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise QuoteProviderError("Current quote provider request failed") from exc

        if not isinstance(payload, dict):
            raise QuoteProviderError("Current quote provider returned invalid JSON payload")

        return _quote_from_payload(payload, fallback_source=self.source_name or _safe_source_from_url(self.url))


def _quote_from_payload(payload: dict[str, Any], fallback_source: str) -> CurrentQuote:
    price = _first_present(payload, ["price", "current_price", "close"])
    if price is None:
        raise QuoteProviderError("Current quote provider payload missing price/current_price/close")

    try:
        current_price = float(price)
    except (TypeError, ValueError) as exc:
        raise QuoteProviderError("Current quote provider payload contains invalid price") from exc
    if not isfinite(current_price) or current_price <= 0:
        raise QuoteProviderError("Current quote provider payload contains invalid price")

    timestamp = _parse_timestamp(payload.get("timestamp") or payload.get("data_timestamp"))
    data_source = str(payload.get("source") or fallback_source)
    symbol = str(payload.get("symbol") or "XAUUSD")

    try:
        return CurrentQuote(
            symbol=symbol,
            current_price=current_price,
            data_source=data_source,
            data_timestamp=timestamp,
        )
    except ValidationError as exc:
        raise QuoteProviderError(f"Current quote provider payload is invalid: {exc.errors()[0]['msg']}") from exc


def _first_present(payload: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def _parse_timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(value, tz=UTC)
    else:
        rendered = str(value).strip()
        if rendered.endswith("Z"):
            rendered = f"{rendered[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(rendered)
        except ValueError as exc:
            raise QuoteProviderError("Current quote provider payload contains invalid timestamp") from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _safe_source_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc
    return "configured-current-quote-provider"
