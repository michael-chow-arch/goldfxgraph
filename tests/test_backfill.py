from __future__ import annotations

import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from goldfxgraph.backfill.cli import main as backfill_main
from goldfxgraph.backfill.eod_backfill import run_eod_backfill
from goldfxgraph.cli import main as goldfxgraph_main
from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.models import ExternalSourceModel
from goldfxgraph.persistence.database import SessionFactory, create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import DailyBar

pytestmark = pytest.mark.asyncio


def _settings(tmp_path) -> GoldFXGraphSettings:
    return GoldFXGraphSettings(
        xauusd_csv_path=tmp_path / "unused.csv",
        eod_backfill_timezone="America/New_York",
        eod_backfill_cutoff_hour=17,
        eod_backfill_cutoff_minute=0,
    )


async def _repository() -> tuple[SessionFactory, ForecastRepository]:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = ForecastRepository(session_factory)
    await _seed_tradingview_history_source(session_factory)
    await repository.upsert_market_bars(
        [
            DailyBar(
                date=date(2024, 1, 5),
                open=2045,
                high=2060,
                low=2038,
                close=2055,
                source="unit-feed",
                symbol="XAUUSD",
            ),
        ]
    )
    return session_factory, repository


async def _seed_tradingview_history_source(session_factory: SessionFactory) -> None:
    async with session_factory.sessionmaker() as session:
        session.add(
            ExternalSourceModel(
                source_key="tradingview.history",
                source_type="market_data",
                endpoint_url="https://www.tradingview.com/symbols/XAUUSD/?exchange=FX",
                request_config={
                    "http_url": "https://tvc4.tradingview.com/history",
                    "ws_url": "wss://data.tradingview.com/socket.io/websocket",
                    "origin": "https://www.tradingview.com",
                    "user_agent": "Mozilla/5.0",
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
                description="测试外部源",
                change_notes="测试数据",
            )
        )
        await session.commit()


async def test_compute_missing_completed_trading_days_respects_us_eastern_cutoff(tmp_path) -> None:
    settings = _settings(tmp_path)
    session_factory, repository = await _repository()

    before_close = datetime(2024, 1, 7, 16, 59, tzinfo=ZoneInfo("America/New_York"))
    after_close = datetime(2024, 1, 7, 17, 1, tzinfo=ZoneInfo("America/New_York"))

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "goldfxgraph.backfill.eod_backfill.fetch_gold_daily_bars",
        lambda **kwargs: [
            DailyBar(
                date=date(2024, 1, 7),
                open=2056.0,
                high=2064.0,
                low=2048.0,
                close=2059.0,
                source="TradingView",
                symbol="XAUUSD",
            )
        ],
    )

    try:
        before_result = await run_eod_backfill(
            settings=settings,
            repository=repository,
            now=before_close,
        )
        after_result = await run_eod_backfill(
            settings=settings,
            repository=repository,
            now=after_close,
        )
    finally:
        monkeypatch.undo()
        await session_factory.engine.dispose()

    assert before_result.missing_dates == []
    assert before_result.written is False
    assert after_result.missing_dates == [date(2024, 1, 7)]
    assert after_result.written is True


async def test_run_eod_backfill_appends_tradingview_history_atomically(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    session_factory, repository = await _repository()
    original_count = await repository.get_market_bars_count()
    monkeypatch.setattr(
        "goldfxgraph.backfill.eod_backfill.fetch_gold_daily_bars",
        lambda **kwargs: [
            DailyBar(
                date=date(2024, 1, 7),
                open=2056.0,
                high=2064.0,
                low=2048.0,
                close=2059.0,
                source="TradingView",
                symbol="XAUUSD",
            )
        ],
    )

    try:
        result = await run_eod_backfill(
            settings=settings,
            repository=repository,
            now=datetime(2024, 1, 7, 17, 1, tzinfo=ZoneInfo("America/New_York")),
        )
        rewritten_count = await repository.get_market_bars_count()
        latest_bar = await repository.get_latest_market_bar()
    finally:
        await session_factory.engine.dispose()

    assert result.appended_dates == [date(2024, 1, 7)]
    assert rewritten_count == original_count + 1
    assert latest_bar is not None
    assert latest_bar.date == date(2024, 1, 7)
    assert latest_bar.source == "TradingView"


async def test_run_eod_backfill_treats_sunday_as_completed_trading_day(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    session_factory, repository = await _repository()
    monkeypatch.setattr(
        "goldfxgraph.backfill.eod_backfill.fetch_gold_daily_bars",
        lambda **kwargs: [
            DailyBar(
                date=date(2024, 1, 7),
                open=2051.0,
                high=2068.0,
                low=2046.0,
                close=2061.0,
                source="TradingView",
                symbol="XAUUSD",
            )
        ],
    )

    try:
        result = await run_eod_backfill(
            settings=settings,
            repository=repository,
            now=datetime(2024, 1, 7, 17, 1, tzinfo=ZoneInfo("America/New_York")),
        )
        latest_bar = await repository.get_latest_market_bar()
    finally:
        await session_factory.engine.dispose()

    assert result.status == "written"
    assert result.written is True
    assert result.target_date == date(2024, 1, 7)
    assert result.missing_dates == [date(2024, 1, 7)]
    assert result.appended_dates == [date(2024, 1, 7)]
    assert latest_bar is not None
    assert latest_bar.date == date(2024, 1, 7)


async def test_run_eod_backfill_fails_when_history_source_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    session_factory, repository = await _repository()
    original_count = await repository.get_market_bars_count()
    monkeypatch.setattr("goldfxgraph.backfill.eod_backfill.fetch_gold_daily_bars", lambda **kwargs: [])

    try:
        result = await run_eod_backfill(
            settings=settings,
            repository=repository,
            now=datetime(2024, 1, 7, 17, 1, tzinfo=ZoneInfo("America/New_York")),
        )
        rewritten_count = await repository.get_market_bars_count()
        latest_bar = await repository.get_latest_market_bar()
    finally:
        await session_factory.engine.dispose()

    assert result.status == "failed"
    assert result.failed is True
    assert result.missing_dates == [date(2024, 1, 7)]
    assert result.failure_reason is not None
    assert rewritten_count == original_count
    assert latest_bar is not None
    assert latest_bar.date == date(2024, 1, 5)


async def test_run_eod_backfill_fails_when_database_has_no_completed_daily_bars(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = ForecastRepository(session_factory)

    try:
        result = await run_eod_backfill(
            settings=settings,
            repository=repository,
            now=datetime(2024, 1, 7, 17, 1, tzinfo=ZoneInfo("America/New_York")),
        )
    finally:
        await session_factory.engine.dispose()

    assert result.status == "failed"
    assert result.failed is True
    assert result.latest_existing_date is None
    assert result.failure_reason is not None


async def test_run_eod_backfill_uses_tradingview_history_when_agent_is_not_provided(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    session_factory, repository = await _repository()

    monkeypatch.setattr(
        "goldfxgraph.backfill.eod_backfill.fetch_gold_daily_bars",
        lambda **kwargs: [
            DailyBar(
                date=date(2024, 1, 7),
                open=2056.0,
                high=2064.0,
                low=2048.0,
                close=2059.0,
                source="TradingView",
                symbol="XAUUSD",
            )
        ],
    )

    try:
        result = await run_eod_backfill(
            settings=settings,
            repository=repository,
            now=datetime(2024, 1, 7, 17, 1, tzinfo=ZoneInfo("America/New_York")),
        )
        latest_bar = await repository.get_latest_market_bar()
    finally:
        await session_factory.engine.dispose()

    assert result.status == "written"
    assert result.written is True
    assert result.appended_dates == [date(2024, 1, 7)]
    assert latest_bar is not None
    assert latest_bar.source == "TradingView"


async def test_goldfxgraph_cli_dispatches_backfill_command(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run_eod_backfill(**kwargs: object) -> object:
        captured.update(kwargs)
        return type(
            "Result",
            (),
            {
                "written": False,
                "status": "no-op",
                "missing_dates": [],
                "appended_dates": [],
                "latest_existing_date": date(2024, 1, 5),
            },
        )()

    monkeypatch.setattr("goldfxgraph.backfill.cli.run_eod_backfill", fake_run_eod_backfill)
    monkeypatch.setattr("goldfxgraph.backfill.cli.create_session_factory", lambda database_url: _FakeSessionFactory())
    monkeypatch.setattr("goldfxgraph.backfill.cli.init_models", lambda engine: asyncio.sleep(0))

    exit_code = await asyncio.to_thread(
        goldfxgraph_main,
        [
            "backfill",
            "--as-of",
            "2024-01-08T17:01:00-05:00",
        ],
    )

    assert exit_code == 0
    assert "csv_path" not in captured
    assert isinstance(captured["settings"], GoldFXGraphSettings)
    assert isinstance(captured["now"], datetime)


async def test_backfill_cli_module_can_run_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run_eod_backfill(**kwargs: object) -> object:
        captured.update(kwargs)
        return type(
            "Result",
            (),
            {
                "written": False,
                "status": "no-op",
                "missing_dates": [],
                "appended_dates": [],
                "latest_existing_date": date(2024, 1, 5),
            },
        )()

    monkeypatch.setattr("goldfxgraph.backfill.cli.run_eod_backfill", fake_run_eod_backfill)
    monkeypatch.setattr("goldfxgraph.backfill.cli.create_session_factory", lambda database_url: _FakeSessionFactory())
    monkeypatch.setattr("goldfxgraph.backfill.cli.init_models", lambda engine: asyncio.sleep(0))

    exit_code = await asyncio.to_thread(
        backfill_main,
        [
            "--as-of",
            "2024-01-08T17:01:00-05:00",
        ],
    )

    assert exit_code == 0
    assert "csv_path" not in captured
    assert isinstance(captured["settings"], GoldFXGraphSettings)
    assert isinstance(captured["now"], datetime)


async def test_backfill_cli_returns_non_zero_when_backfill_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_eod_backfill(**kwargs: object) -> object:
        return type(
            "Result",
            (),
            {
                "written": False,
                "status": "failed",
                "missing_dates": [date(2024, 1, 8)],
                "appended_dates": [],
                "latest_existing_date": date(2024, 1, 5),
                "target_date": date(2024, 1, 8),
                "failure_reason": "TradingView history unavailable",
            },
        )()

    monkeypatch.setattr("goldfxgraph.backfill.cli.run_eod_backfill", fake_run_eod_backfill)
    monkeypatch.setattr("goldfxgraph.backfill.cli.create_session_factory", lambda database_url: _FakeSessionFactory())
    monkeypatch.setattr("goldfxgraph.backfill.cli.init_models", lambda engine: asyncio.sleep(0))

    exit_code = await asyncio.to_thread(
        backfill_main,
        [
            "--as-of",
            "2024-01-08T17:01:00-05:00",
        ],
    )

    assert exit_code == 1


class _FakeEngine:
    async def dispose(self) -> None:  # pragma: no cover - trivial helper
        return None


class _FakeSessionFactory:
    def __init__(self) -> None:
        self.engine = _FakeEngine()
