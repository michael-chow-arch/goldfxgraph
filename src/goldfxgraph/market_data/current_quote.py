from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import httpx

from goldfxgraph.persistence.external_source_registry import ExternalSourceSnapshot
from goldfxgraph.schemas.forecast import CurrentQuote


class QuoteProviderError(RuntimeError):
    """当前报价 provider 返回无效数据或请求失败。"""


class CurrentQuoteProvider:
    def __init__(
        self,
        source: ExternalSourceSnapshot | None = None,
        api_key: str | None = None,
        source_name: str | None = None,
        candidate_urls: list[str] | None = None,
        transport: httpx.BaseTransport | None = None,
        socket_factory: Callable[..., AbstractContextManager[Any]] | None = None,
    ) -> None:
        self.source = source
        self.api_key = api_key
        self.source_name = source_name
        self.candidate_urls = candidate_urls
        self.transport = transport
        self.socket_factory = socket_factory

    def fetch(self) -> CurrentQuote:
        from goldfxgraph.market_data.tradingview_quote import TradingViewQuoteProvider

        if self.source is None:
            raise QuoteProviderError("TradingView quote source is required")
        provider = TradingViewQuoteProvider(
            source=self.source,
            transport=self.transport,
            socket_factory=self.socket_factory,
        )
        return provider.fetch()
