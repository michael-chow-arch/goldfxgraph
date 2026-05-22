from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from goldfxgraph.schemas.forecast import DailyBar, MarketDataSet


class CsvValidationError(ValueError):
    """CSV 市场数据无法通过结构或数值校验。"""


REQUIRED_COLUMNS = {"date", "open", "high", "low", "close"}
OPTIONAL_COLUMNS = {"volume", "source", "symbol"}


def load_xauusd_daily_csv(path: Path) -> MarketDataSet:
    if not path.exists():
        raise CsvValidationError(f"CSV file not found: {path}")

    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        raise CsvValidationError(f"CSV file could not be read: {path}") from exc

    if frame.empty:
        raise CsvValidationError("CSV file is empty")

    frame = frame.rename(columns={column: str(column).strip().lower() for column in frame.columns})
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise CsvValidationError(f"CSV missing required columns: {', '.join(missing)}")

    selected_columns = [*REQUIRED_COLUMNS, *(column for column in OPTIONAL_COLUMNS if column in frame.columns)]
    normalized = frame.loc[:, selected_columns].copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.date

    for column in ["open", "high", "low", "close"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    if "volume" in normalized.columns:
        normalized["volume"] = pd.to_numeric(normalized["volume"], errors="coerce")

    invalid_columns = [column for column in ["date", "open", "high", "low", "close"] if normalized[column].isna().any()]
    if invalid_columns:
        raise CsvValidationError(f"CSV contains invalid data in columns: {', '.join(invalid_columns)}")

    normalized = normalized.sort_values("date", ascending=True).reset_index(drop=True)
    bars = []
    for record in normalized.to_dict("records"):
        try:
            bars.append(_record_to_daily_bar(record))
        except ValidationError as exc:
            raise CsvValidationError(f"CSV contains invalid OHLC data: {exc.errors()[0]['msg']}") from exc
    if not bars:
        raise CsvValidationError("CSV file has no valid daily bars")

    latest_bar = bars[-1]
    return MarketDataSet(symbol=latest_bar.symbol, bars=bars, latest_bar=latest_bar)


def _record_to_daily_bar(record: dict[str, Any]) -> DailyBar:
    source = _optional_string(record.get("source"))
    symbol = _optional_string(record.get("symbol")) or "XAUUSD"
    return DailyBar(
        date=record["date"],
        open=float(record["open"]),
        high=float(record["high"]),
        low=float(record["low"]),
        close=float(record["close"]),
        volume=_optional_float(record.get("volume")),
        source=source,
        symbol=symbol,
    )


def _optional_string(value: Any) -> str | None:
    if _is_missing_scalar(value):
        return None
    rendered = str(value).strip()
    return rendered or None


def _optional_float(value: Any) -> float | None:
    if _is_missing_scalar(value):
        return None
    return float(value)


def _is_missing_scalar(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
