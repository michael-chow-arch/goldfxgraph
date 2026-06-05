from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import httpx
import pytest

from goldfxgraph.persistence.external_source_registry import ExternalSourceSnapshot


def _tradingview_history_source() -> ExternalSourceSnapshot:
    return ExternalSourceSnapshot(
        id=1,
        source_key="tradingview.history",
        source_type="market_data",
        endpoint_url="https://www.tradingview.com/symbols/XAUUSD/?exchange=FX",
        request_config={
            "http_url": "https://tvc4.tradingview.com/history",
            "ws_url": "wss://data.tradingview.com/socket.io/websocket",
            "origin": "https://www.tradingview.com",
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "auth_token": "unauthorized_user_token",
            "chart_symbol": "FX:XAUUSD",
            "chart_symbol_alias": "symbol_1",
            "chart_timezone": "Etc/UTC",
            "session_prefix": "cs_",
            "session_path": "symbols/XAUUSD/",
            "symbol": "XAUUSD",
            "source_name": "TradingView",
        },
        version="1.0.0",
        is_active=True,
        description=None,
        change_notes=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_fetch_gold_daily_bars_parses_valid_completed_rows_and_skips_invalid_ones() -> None:
    from goldfxgraph.market_data.tradingview_history import fetch_gold_daily_bars

    start_date = date(2024, 1, 2)
    end_date = date(2024, 1, 8)
    period1 = int(datetime.combine(start_date, time.min, tzinfo=UTC).timestamp())
    period2 = int(datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC).timestamp())
    payload = {
        "s": "ok",
        "t": [
            1704153600,
            1704240000,
            1704308400,
            1704844800,
            1704931200,
            1705017600,
            1705104000,
            1705190400,
        ],
        "o": [2050.0, 2055.0, 2060.0, 2065.0, 2070.0, 2075.0, 2080.0, 2085.0],
        "h": [2060.0, 2065.0, 2070.0, 2075.0, 2080.0, 2085.0, 2090.0, 2095.0],
        "l": [2040.0, 2045.0, 2050.0, 2055.0, 2060.0, 2065.0, 2070.0, 2075.0],
        "c": [2055.0, 2060.0, 2065.0, 2070.0, 2075.0, 2080.0, 2085.0, 2090.0],
        "v": [10, 11, 12, 13, 14, 15, 16, 17],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/history"
        assert request.url.params["symbol"] == "XAUUSD"
        assert request.url.params["resolution"] == "D"
        assert request.url.params["from"] == str(period1)
        assert request.url.params["to"] == str(period2)
        return httpx.Response(200, json=payload, request=request)

    bars = fetch_gold_daily_bars(
        source=_tradingview_history_source(),
        start_date=start_date,
        end_date=end_date,
        transport=httpx.MockTransport(handler),
    )

    assert [bar.date.isoformat() for bar in bars] == ["2024-01-02", "2024-01-03"]
    assert bars[0].open == 2050.0
    assert bars[0].source == "TradingView"
    assert bars[0].symbol == "XAUUSD"
    assert bars[1].close == 2060.0


def test_fetch_gold_daily_bars_rejects_conflicting_dates() -> None:
    from goldfxgraph.market_data.tradingview_history import fetch_gold_daily_bars

    start_date = date(2024, 1, 2)
    end_date = date(2024, 1, 4)
    payload = {
        "s": "ok",
        "t": [1704153600, 1704153600, 1704240000],
        "o": [2050.0, 2050.0, 2060.0],
        "h": [2060.0, 2062.0, 2070.0],
        "l": [2040.0, 2040.0, 2050.0],
        "c": [2055.0, 2056.0, 2065.0],
        "v": [10, 10, 12],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    from goldfxgraph.market_data.tradingview_history import TradingViewHistoryError

    with pytest.raises(TradingViewHistoryError, match="conflicting daily bars"):
        fetch_gold_daily_bars(
            source=_tradingview_history_source(),
            start_date=start_date,
            end_date=end_date,
            transport=httpx.MockTransport(handler),
        )


def test_fetch_gold_daily_bars_skips_unfinished_daily_rows_and_invalid_payload_rows() -> None:
    from goldfxgraph.market_data.tradingview_history import fetch_gold_daily_bars

    start_date = date(2024, 1, 2)
    end_date = date(2024, 1, 5)
    payload = {
        "s": "ok",
        "t": [1704153600, 1704240000, 1704308400],
        "o": [2050.0, 2055.0, None],
        "h": [2060.0, 2040.0, 2070.0],
        "l": [2040.0, 2045.0, 2050.0],
        "c": [2055.0, 2060.0, 2065.0],
        "v": [10, 11, 12],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    bars = fetch_gold_daily_bars(
        source=_tradingview_history_source(),
        start_date=start_date,
        end_date=end_date,
        transport=httpx.MockTransport(handler),
    )

    assert [bar.date.isoformat() for bar in bars] == ["2024-01-02"]


def test_fetch_gold_daily_bars_returns_empty_list_for_no_data() -> None:
    from goldfxgraph.market_data.tradingview_history import fetch_gold_daily_bars

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"s": "no_data"}, request=request)

    bars = fetch_gold_daily_bars(
        source=_tradingview_history_source(),
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 5),
        transport=httpx.MockTransport(handler),
    )

    assert bars == []


def test_extract_daily_bars_from_timescale_update_parses_tradingview_series_rows() -> None:
    from goldfxgraph.market_data.tradingview_history import _extract_daily_bars_from_timescale_update

    message = {
        "m": "timescale_update",
        "p": [
            "cs_sample",
            {
                "s1": {
                    "node": "hkg1-charts-free-4-series-rtkev-2",
                    "s": [
                        {"i": 0, "v": [1779224400.0, 4484.735, 4553.045, 4453.39, 4543.705, 773910.0]},
                        {"i": 1, "v": [1779310800.0, 4544.62, 4570.895, 4488.63, 4543.425, 901259.0]},
                        {"i": 2, "v": [1779397200.0, 4544.905, 4545.26, 4491.93, 4509.69, 659163.0]},
                        {"i": 3, "v": [1779483600.0, None, 1, 1, 1, 1]},
                        {"i": 4, "v": [1779656400.0, 4550.54, 4580.21, 4548.91, 4570.315, 400869.0]},
                        {"i": 5, "v": [1779742800.0, 4571.33, 4580.245, 4527.865, 4534.9, 114679.0]},
                    ],
                }
            },
        ],
    }

    bars = _extract_daily_bars_from_timescale_update(
        message,
        start_date=date(2026, 5, 19),
        end_date=date(2026, 5, 25),
    )

    assert [bar.date.isoformat() for bar in bars] == [
        "2026-05-19",
        "2026-05-20",
        "2026-05-21",
        "2026-05-24",
        "2026-05-25",
    ]
    assert bars[0].open == 4484.735
    assert bars[-1].close == 4534.9
