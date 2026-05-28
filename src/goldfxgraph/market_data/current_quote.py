from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import httpx

from goldfxgraph.schemas.forecast import CurrentQuote


class QuoteProviderError(RuntimeError):
    """当前报价 provider 返回无效数据或请求失败。"""


DEFAULT_TRADINGVIEW_URL = "https://www.tradingview.com/symbols/XAUUSD/?exchange=FX"


class CurrentQuoteProvider:
    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        source_name: str | None = None,
        candidate_urls: list[str] | None = None,
        transport: httpx.BaseTransport | None = None,
        socket_factory: Callable[..., AbstractContextManager[Any]] | None = None,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.source_name = source_name
        self.candidate_urls = candidate_urls
        self.transport = transport
        self.socket_factory = socket_factory

    def fetch(self) -> CurrentQuote:
        from goldfxgraph.market_data.tradingview_quote import TradingViewQuoteProvider

        provider = TradingViewQuoteProvider(
            url=_normalize_tradingview_url(self.url),
            transport=self.transport,
            socket_factory=self.socket_factory,
        )
        return provider.fetch()


def _normalize_tradingview_url(url: str | None) -> str:
    return DEFAULT_TRADINGVIEW_URL
