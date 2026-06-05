from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from goldfxgraph.cli import main as goldfxgraph_main
from goldfxgraph.market_data import tradingview_history
from goldfxgraph.market_data.csv_loader import CsvValidationError, load_xauusd_daily_csv
from goldfxgraph.market_data.current_quote import CurrentQuoteProvider, QuoteProviderError
from goldfxgraph.market_data.ingest import import_xauusd_daily_csv_to_db
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.external_source_registry import ExternalSourceSnapshot
from goldfxgraph.persistence.repositories import MarketDataRepository
from goldfxgraph.schemas.forecast import DailyBar


class FakeQuoteSocket:
    def __init__(self, frames: list[str | bytes]) -> None:
        self.frames = frames
        self.sent_messages: list[str] = []
        self._index = 0

    def __enter__(self) -> "FakeQuoteSocket":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def send(self, message: str) -> None:
        self.sent_messages.append(message)

    def recv(self, timeout: float | None = None) -> str | bytes:
        if self._index >= len(self.frames):
            raise TimeoutError("fake socket exhausted")
        frame = self.frames[self._index]
        self._index += 1
        return frame


def _build_socket_factory(frames: list[str | bytes], captured: list[dict[str, Any]]) -> Any:
    def factory(**kwargs: Any) -> FakeQuoteSocket:
        captured.append(kwargs)
        return FakeQuoteSocket(frames)

    return factory


def _socket_frame(payload: str) -> str:
    return f"~m~{len(payload)}~m~{payload}"


def _tradingview_source_snapshot() -> ExternalSourceSnapshot:
    return ExternalSourceSnapshot(
        id=1,
        source_key="tradingview.current_quote",
        source_type="market_data",
        endpoint_url="https://www.tradingview.com/symbols/XAUUSD/?exchange=FX",
        request_config={
            "socket_url": "wss://data.tradingview.com/socket.io/websocket",
            "socket_from": "symbols/XAUUSD/",
            "auth": "unauthorized_user_token",
            "origin": "https://www.tradingview.com",
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "symbol": "FX:XAUUSD",
            "source_name": "TradingView",
        },
        version="1.0.0",
        is_active=True,
        description=None,
        change_notes=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _tradingview_history_source_snapshot() -> ExternalSourceSnapshot:
    return ExternalSourceSnapshot(
        id=2,
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


def test_load_xauusd_daily_csv_sorts_and_preserves_optional_fields(tmp_path: Path) -> None:
    csv_path = tmp_path / "xauusd.csv"
    csv_path.write_text(
        "Date,Open,High,Low,Close,Volume,Source,Symbol\n"
        "2024-01-02,2050,2060,2040,2055,10,unit,XAUUSD\n"
        "2024-01-01,2040,2050,2030,2045,9,unit,XAUUSD\n",
        encoding="utf-8",
    )

    result = load_xauusd_daily_csv(csv_path)

    assert result.latest_bar.date.isoformat() == "2024-01-02"
    assert result.latest_bar.close == 2055
    assert result.latest_bar.source == "unit"
    assert result.latest_bar.symbol == "XAUUSD"
    assert len(result.bars) == 2


def test_load_repository_csv_fixture() -> None:
    result = load_xauusd_daily_csv(Path("data/raw/xauusd_daily.csv"))

    assert result.latest_bar.close > 0
    assert result.bars[0].date <= result.latest_bar.date


def test_load_xauusd_daily_csv_rejects_missing_required_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("Date,Open,High,Close\n2024-01-01,1,2,3\n", encoding="utf-8")

    with pytest.raises(CsvValidationError, match="low"):
        load_xauusd_daily_csv(csv_path)


def test_load_xauusd_daily_csv_rejects_invalid_ohlc_range(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad-range.csv"
    csv_path.write_text("Date,Open,High,Low,Close\n2024-01-01,2050,2040,2030,2055\n", encoding="utf-8")

    with pytest.raises(CsvValidationError, match="within low/high range"):
        load_xauusd_daily_csv(csv_path)


@pytest.mark.asyncio
async def test_import_xauusd_daily_csv_to_db_writes_rows_and_keeps_latest_bar(tmp_path: Path) -> None:
    csv_path = tmp_path / "xauusd.csv"
    csv_path.write_text(
        "date,open,high,low,close,volume,source,symbol\n"
        "2024-01-01,2040,2050,2030,2045,9,unit,XAUUSD\n"
        "2024-01-02,2050,2060,2040,2055,10,unit,XAUUSD\n",
        encoding="utf-8",
    )

    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = MarketDataRepository(session_factory)

    written = await import_xauusd_daily_csv_to_db(csv_path, repository)

    latest = await repository.get_latest_market_bar("XAUUSD")
    count = await repository.get_market_bars_count("XAUUSD")

    assert written == 2
    assert count == 2
    assert latest is not None
    assert latest.date.isoformat() == "2024-01-02"
    assert latest.close == 2055
    assert latest.source == "unit"


@pytest.mark.asyncio
async def test_import_xauusd_daily_csv_to_db_is_idempotent(tmp_path: Path) -> None:
    csv_path = tmp_path / "xauusd.csv"
    csv_path.write_text(
        "date,open,high,low,close,volume,source,symbol\n"
        "2024-01-01,2040,2050,2030,2045,9,unit,XAUUSD\n"
        "2024-01-02,2050,2060,2040,2055,10,unit,XAUUSD\n",
        encoding="utf-8",
    )

    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = MarketDataRepository(session_factory)

    first_written = await import_xauusd_daily_csv_to_db(csv_path, repository)
    second_written = await import_xauusd_daily_csv_to_db(csv_path, repository)
    count = await repository.get_market_bars_count("XAUUSD")

    assert first_written == 2
    assert second_written == 2
    assert count == 2


@pytest.mark.asyncio
async def test_import_xauusd_daily_csv_to_db_rejects_missing_required_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("date,open,high,close\n2024-01-01,1,2,3\n", encoding="utf-8")

    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    repository = MarketDataRepository(session_factory)

    with pytest.raises(CsvValidationError, match="low"):
        await import_xauusd_daily_csv_to_db(csv_path, repository)


def test_daily_bar_rejects_non_finite_or_negative_values() -> None:
    from datetime import date

    with pytest.raises(ValueError):
        DailyBar(date=date(2024, 1, 1), open=-1, high=1, low=1, close=1)

    with pytest.raises(ValueError):
        DailyBar(date=date(2024, 1, 1), open=1, high=float("inf"), low=1, close=1)


def test_current_quote_provider_uses_tradingview_only_and_ignores_legacy_candidates() -> None:
    captured: list[dict[str, Any]] = []
    socket_factory = _build_socket_factory(
        [
            _socket_frame('{"m":"qsd","p":["qs_goldfxgraph",{"n":"FX:XAUUSD","s":"ok","v":{"lp":4427.31}}]}'),
            _socket_frame('{"m":"qsd","p":["qs_goldfxgraph",{"n":"FX:XAUUSD","s":"ok","v":{"lp_time":1779890056}}]}'),
        ],
        captured,
    )

    provider = CurrentQuoteProvider(
        source=_tradingview_source_snapshot(),
        socket_factory=socket_factory,
    )

    quote = provider.fetch()

    assert captured[0]["socket_url"].startswith(
        "wss://data.tradingview.com/socket.io/websocket?from=symbols%2FXAUUSD%2F&date="
    )
    assert captured[0]["origin"] == "https://www.tradingview.com"
    assert captured[0]["referer"] == "https://www.tradingview.com/symbols/XAUUSD/?exchange=FX"
    assert quote.symbol == "XAUUSD"
    assert quote.current_price == 4427.31
    assert quote.data_source == "TradingView"
    assert quote.data_timestamp.isoformat() == "2026-05-27T13:54:16+00:00"


def test_tradingview_quote_provider_parses_quote_websocket_frames() -> None:
    from goldfxgraph.market_data.tradingview_quote import TradingViewQuoteProvider

    captured: list[dict[str, Any]] = []
    socket_factory = _build_socket_factory(
        [
            _socket_frame('{"session_id":"0.107699286.0_sin1-charts-free-3-tvbs-dr6j5-5"}'),
            _socket_frame(
                '{"m":"qsd","p":["qs_goldfxgraph",{"n":"FX:XAUUSD","s":"ok","v":{"lp":4431.35,"lp_time":1779890010}}]}'
            ),
            _socket_frame('{"m":"quote_completed","p":["qs_goldfxgraph","FX:XAUUSD"]}'),
        ],
        captured,
    )

    provider = TradingViewQuoteProvider(source=_tradingview_source_snapshot(), socket_factory=socket_factory)

    quote = provider.fetch()

    assert quote.symbol == "XAUUSD"
    assert quote.current_price == 4431.35
    assert quote.data_source == "TradingView"
    assert quote.data_timestamp.isoformat() == "2026-05-27T13:53:30+00:00"
    assert captured[0]["origin"] == "https://www.tradingview.com"
    assert captured[0]["referer"] == "https://www.tradingview.com/symbols/XAUUSD/?exchange=FX"


def test_tradingview_quote_provider_rejects_missing_lp_time() -> None:
    from goldfxgraph.market_data.tradingview_quote import TradingViewQuoteProvider

    socket_factory = _build_socket_factory(
        [_socket_frame('{"m":"qsd","p":["qs_goldfxgraph",{"n":"FX:XAUUSD","s":"ok","v":{"lp":4431.35}}]}')],
        [],
    )
    provider = TradingViewQuoteProvider(source=_tradingview_source_snapshot(), socket_factory=socket_factory)

    with pytest.raises(QuoteProviderError, match="TradingView quote websocket missing live price or timestamp"):
        provider.fetch()


def test_tradingview_quote_provider_rejects_malformed_socket_payload() -> None:
    from goldfxgraph.market_data.tradingview_quote import TradingViewQuoteProvider

    socket_factory = _build_socket_factory(["not-a-socket-frame"], [])
    provider = TradingViewQuoteProvider(source=_tradingview_source_snapshot(), socket_factory=socket_factory)

    with pytest.raises(QuoteProviderError, match="TradingView quote websocket missing live price or timestamp"):
        provider.fetch()


def test_tradingview_quote_provider_raises_on_network_failure() -> None:
    from goldfxgraph.market_data.tradingview_quote import TradingViewQuoteProvider

    def socket_factory(**kwargs: Any) -> FakeQuoteSocket:
        raise ConnectionError("network down")

    provider = TradingViewQuoteProvider(source=_tradingview_source_snapshot(), socket_factory=socket_factory)

    with pytest.raises(QuoteProviderError, match="TradingView quote request failed"):
        provider.fetch()


def test_current_quote_provider_ignores_non_tradingview_url_override() -> None:
    captured: list[dict[str, Any]] = []
    socket_factory = _build_socket_factory(
        [
            _socket_frame('{"m":"qsd","p":["qs_goldfxgraph",{"n":"FX:XAUUSD","s":"ok","v":{"lp":4431.35}}]}'),
            _socket_frame('{"m":"qsd","p":["qs_goldfxgraph",{"n":"FX:XAUUSD","s":"ok","v":{"lp_time":1779890010}}]}'),
        ],
        captured,
    )

    provider = CurrentQuoteProvider(
        source=_tradingview_source_snapshot(),
        socket_factory=socket_factory,
    )

    quote = provider.fetch()

    assert captured[0]["socket_url"].startswith(
        "wss://data.tradingview.com/socket.io/websocket?from=symbols%2FXAUUSD%2F&date="
    )
    assert quote.symbol == "XAUUSD"
    assert quote.current_price == 4431.35
    assert quote.data_source == "TradingView"


def test_yahoo_history_fetcher_is_removed_from_daily_bar_backfill() -> None:
    from datetime import date

    from goldfxgraph.market_data.yahoo_history import YahooHistoryError, fetch_gold_daily_bars

    with pytest.raises(YahooHistoryError, match="removed; use TradingView history instead"):
        fetch_gold_daily_bars(
            start_date=date(2026, 5, 23),
            end_date=date(2026, 5, 26),
        )


def test_tradingview_history_websocket_disables_proxy_and_parses_daily_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    session_id = "cs_123"
    update_payload = (
        '{"m":"timescale_update","p":["cs_123",{"s1":{"s":[{"v":[1778544000,4700.0,4710.0,4680.0,4695.0,1234]}]}}]}'
    )
    completed_payload = '{"m":"series_completed","p":["cs_123","s1"]}'

    class FakeHistorySocket:
        def __init__(self) -> None:
            self.sent_messages: list[str] = []
            self._frames = [
                f"~m~{len(update_payload)}~m~{update_payload}~m~{len(completed_payload)}~m~{completed_payload}"
            ]
            self._index = 0

        def __enter__(self) -> "FakeHistorySocket":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

        def send(self, message: str) -> None:
            self.sent_messages.append(message)

        def recv(self, timeout: float | None = None) -> str:
            if self._index >= len(self._frames):
                raise TimeoutError("fake history socket exhausted")
            frame = self._frames[self._index]
            self._index += 1
            return frame

    def fake_connect(*args: Any, **kwargs: Any) -> FakeHistorySocket:
        captured.update(kwargs)
        return FakeHistorySocket()

    monkeypatch.setattr(tradingview_history, "_random_session_id", lambda prefix: session_id)
    monkeypatch.setattr(tradingview_history, "connect", fake_connect)

    bars = tradingview_history.fetch_gold_daily_bars(
        source=_tradingview_history_source_snapshot(),
        start_date=date(2026, 5, 12),
        end_date=date(2026, 5, 12),
    )

    assert captured["proxy"] is None
    assert bars[0].date == date(2026, 5, 12)
    assert bars[0].open == 4700.0
    assert bars[0].source == "TradingView"


def test_goldfxgraph_cli_dispatches_import_market_data_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv_path = tmp_path / "xauusd.csv"
    captured: dict[str, object] = {}

    def fake_main(argv: list[str] | None = None) -> int:
        captured["argv"] = list(argv or [])
        return 0

    monkeypatch.setattr("goldfxgraph.market_data.ingest.main", fake_main)

    exit_code = goldfxgraph_main(
        [
            "import-market-data",
            "--csv-path",
            str(csv_path),
            "--symbol",
            "XAUUSD",
            "--env-file",
            "dev.env",
        ]
    )

    assert exit_code == 0
    assert captured["argv"] == [
        "--csv-path",
        str(csv_path),
        "--symbol",
        "XAUUSD",
        "--env-file",
        "dev.env",
    ]
