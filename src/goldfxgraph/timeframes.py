from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def trading_day_for_timestamp(
    timestamp: datetime,
    *,
    timezone_name: str,
    cutoff_hour: int,
    cutoff_minute: int,
) -> date:
    local_time = timestamp.astimezone(ZoneInfo(timezone_name))
    trading_day = local_time.date()
    cutoff = time(hour=cutoff_hour, minute=cutoff_minute)
    local_clock = local_time.time()

    if local_time.weekday() == 5:
        trading_day -= timedelta(days=1)
    elif local_time.weekday() == 6 and local_clock < cutoff:
        trading_day -= timedelta(days=2)
    elif local_clock < cutoff:
        trading_day -= timedelta(days=1)

    return trading_day
