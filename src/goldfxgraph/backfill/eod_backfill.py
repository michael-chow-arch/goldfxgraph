from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from goldfxgraph.market_data.tradingview_history import TradingViewHistoryError, fetch_gold_daily_bars
from goldfxgraph.persistence.repositories import ForecastRepository


@dataclass(slots=True)
class BackfillResult:
    latest_existing_date: date | None
    target_date: date
    missing_dates: list[date]
    appended_dates: list[date]
    status: Literal["written", "no-op", "failed"]
    failure_reason: str | None = None

    @property
    def written(self) -> bool:
        return self.status == "written"

    @property
    def failed(self) -> bool:
        return self.status == "failed"


async def run_eod_backfill(
    *,
    settings,
    repository: ForecastRepository,
    now: datetime | None = None,
) -> BackfillResult:
    latest_existing_bar = await repository.get_latest_market_bar("XAUUSD")
    if latest_existing_bar is None:
        target_date = _latest_completed_trading_day(
            now=now or datetime.now(UTC),
            timezone_name=settings.eod_backfill_timezone,
            cutoff_hour=settings.eod_backfill_cutoff_hour,
            cutoff_minute=settings.eod_backfill_cutoff_minute,
        )
        return BackfillResult(
            latest_existing_date=None,
            target_date=target_date,
            missing_dates=[],
            appended_dates=[],
            status="failed",
            failure_reason="数据库中没有可用于补齐的 completed daily bars",
        )

    latest_existing_date = latest_existing_bar.date
    target_date = _latest_completed_trading_day(
        now=now or datetime.now(UTC),
        timezone_name=settings.eod_backfill_timezone,
        cutoff_hour=settings.eod_backfill_cutoff_hour,
        cutoff_minute=settings.eod_backfill_cutoff_minute,
    )

    missing_dates = _missing_trading_days(latest_existing_date, target_date)
    if not missing_dates:
        return BackfillResult(
            latest_existing_date=latest_existing_date,
            target_date=target_date,
            missing_dates=[],
            appended_dates=[],
            status="no-op",
        )

    try:
        appended_bars = fetch_gold_daily_bars(
            start_date=missing_dates[0],
            end_date=missing_dates[-1],
        )
    except TradingViewHistoryError:
        return BackfillResult(
            latest_existing_date=latest_existing_date,
            target_date=target_date,
            missing_dates=missing_dates,
            appended_dates=[],
            status="failed",
            failure_reason="TradingView 历史日线拉取失败",
        )

    if not appended_bars:
        return BackfillResult(
            latest_existing_date=latest_existing_date,
            target_date=target_date,
            missing_dates=missing_dates,
            appended_dates=[],
            status="failed",
            failure_reason="TradingView 未返回任何可写入的 completed daily bars",
        )

    appended_dates = [bar.date for bar in appended_bars]
    if appended_dates != missing_dates:
        missing_returned_dates = [bar_date for bar_date in missing_dates if bar_date not in appended_dates]
        return BackfillResult(
            latest_existing_date=latest_existing_date,
            target_date=target_date,
            missing_dates=missing_dates,
            appended_dates=appended_dates,
            status="failed",
            failure_reason=(
                "TradingView 返回的 completed daily bars 未覆盖全部缺口日期: "
                + ",".join(item.isoformat() for item in missing_returned_dates)
            ),
        )

    await repository.upsert_market_bars(appended_bars)

    return BackfillResult(
        latest_existing_date=latest_existing_date,
        target_date=target_date,
        missing_dates=missing_dates,
        appended_dates=appended_dates,
        status="written",
    )


def _latest_completed_trading_day(
    *,
    now: datetime,
    timezone_name: str,
    cutoff_hour: int,
    cutoff_minute: int,
) -> date:
    local_now = now.astimezone(ZoneInfo(timezone_name))
    candidate = local_now.date()
    cutoff = time(hour=cutoff_hour, minute=cutoff_minute)
    local_clock = local_now.time()
    if local_now.weekday() == 5:
        candidate -= timedelta(days=1)
    elif local_now.weekday() == 6 and local_clock < cutoff:
        candidate -= timedelta(days=2)
    elif local_clock < cutoff:
        candidate -= timedelta(days=1)

    return candidate


def _missing_trading_days(latest_existing_date: date, target_date: date) -> list[date]:
    if latest_existing_date >= target_date:
        return []

    missing_dates: list[date] = []
    cursor = latest_existing_date + timedelta(days=1)
    while cursor <= target_date:
        if cursor.weekday() != 5:
            missing_dates.append(cursor)
        cursor += timedelta(days=1)
    return missing_dates
