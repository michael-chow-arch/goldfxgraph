from __future__ import annotations

from datetime import date

import httpx

from goldfxgraph.schemas.forecast import DailyBar


class YahooHistoryError(RuntimeError):
    """Yahoo Finance 历史行情拉取失败。"""


def fetch_gold_daily_bars(
    *,
    start_date: date,
    end_date: date,
    transport: httpx.BaseTransport | None = None,
) -> list[DailyBar]:
    raise YahooHistoryError("Yahoo daily bar backfill has been removed; use TradingView history instead")
