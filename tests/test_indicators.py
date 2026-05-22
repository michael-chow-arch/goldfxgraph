from datetime import date

from goldfxgraph.indicators.technical import compute_technical_indicators
from goldfxgraph.schemas.forecast import DailyBar


def _bar(day: int, close: float) -> DailyBar:
    return DailyBar(date=date(2024, 1, day), open=close - 1, high=close + 2, low=close - 2, close=close)


def test_compute_technical_indicators_returns_deterministic_values() -> None:
    bars = [_bar(day, 1900 + day) for day in range(1, 31)]

    indicators = compute_technical_indicators(bars)

    assert indicators.sma_20 == 1920.5
    assert indicators.ema_12 is not None
    assert indicators.rsi_14 is not None
    assert indicators.atr_14 is not None


def test_compute_technical_indicators_marks_unavailable_values() -> None:
    indicators = compute_technical_indicators([_bar(1, 1901)])

    assert indicators.sma_20 is None
    assert "sma_20" in indicators.unavailable
