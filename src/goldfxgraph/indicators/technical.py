from __future__ import annotations

from typing import cast

import pandas as pd

from goldfxgraph.schemas.forecast import DailyBar, TechnicalIndicators


def compute_technical_indicators(bars: list[DailyBar]) -> TechnicalIndicators:
    unavailable: dict[str, str] = {}
    if not bars:
        return TechnicalIndicators(unavailable=_all_unavailable("没有可用的日线数据"))

    frame = pd.DataFrame(
        {
            "high": [bar.high for bar in bars],
            "low": [bar.low for bar in bars],
            "close": [bar.close for bar in bars],
        }
    )
    close = cast(pd.Series, frame["close"])

    sma_20 = _latest_or_unavailable(
        cast(pd.Series, close.rolling(window=20).mean()),
        "sma_20",
        len(bars),
        20,
        unavailable,
    )
    ema_12 = _latest_or_unavailable(
        cast(pd.Series, close.ewm(span=12, adjust=False).mean()),
        "ema_12",
        len(bars),
        12,
        unavailable,
    )
    rsi_14 = _compute_rsi_14(close, unavailable)
    atr_14 = _compute_atr_14(frame, unavailable)

    return TechnicalIndicators(
        sma_20=sma_20,
        ema_12=ema_12,
        rsi_14=rsi_14,
        atr_14=atr_14,
        unavailable=unavailable,
    )


def _latest_or_unavailable(
    series: pd.Series,
    key: str,
    length: int,
    required: int,
    unavailable: dict[str, str],
) -> float | None:
    if length < required:
        unavailable[key] = f"至少需要 {required} 根日线数据，当前只有 {length} 根。"
        return None
    value = series.iloc[-1]
    if pd.isna(value):
        unavailable[key] = "指标结果不可用，请检查输入数据。"
        return None
    return round(float(value), 6)


def _compute_rsi_14(close: pd.Series, unavailable: dict[str, str]) -> float | None:
    if len(close) < 15:
        unavailable["rsi_14"] = f"至少需要 15 根日线数据计算 RSI-14，当前只有 {len(close)} 根。"
        return None

    delta = cast(pd.Series, close.diff())
    gain = cast(pd.Series, delta.clip(lower=0))
    loss = cast(pd.Series, -delta.clip(upper=0))
    average_gain = cast(pd.Series, gain.rolling(window=14).mean())
    average_loss = cast(pd.Series, loss.rolling(window=14).mean())
    latest_gain = average_gain.iloc[-1]
    latest_loss = average_loss.iloc[-1]

    if pd.isna(latest_gain) or pd.isna(latest_loss):
        unavailable["rsi_14"] = "RSI-14 结果不可用，请检查输入数据。"
        return None
    if latest_loss == 0:
        return 100.0

    relative_strength = latest_gain / latest_loss
    return round(float(100 - (100 / (1 + relative_strength))), 6)


def _compute_atr_14(frame: pd.DataFrame, unavailable: dict[str, str]) -> float | None:
    if len(frame) < 15:
        unavailable["atr_14"] = f"至少需要 15 根日线数据计算 ATR-14，当前只有 {len(frame)} 根。"
        return None

    high = cast(pd.Series, frame["high"])
    low = cast(pd.Series, frame["low"])
    close = cast(pd.Series, frame["close"])
    previous_close = cast(pd.Series, close.shift(1))
    true_range = cast(
        pd.Series,
        pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1),
    )
    atr = cast(pd.Series, true_range.rolling(window=14).mean())
    value = atr.iloc[-1]

    if pd.isna(value):
        unavailable["atr_14"] = "ATR-14 结果不可用，请检查输入数据。"
        return None
    return round(float(value), 6)


def _all_unavailable(reason: str) -> dict[str, str]:
    return {
        "sma_20": reason,
        "ema_12": reason,
        "rsi_14": reason,
        "atr_14": reason,
    }
