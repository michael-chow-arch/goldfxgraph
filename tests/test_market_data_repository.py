from datetime import UTC, date, datetime

import pytest
from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect

from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.models import MarketDataBarModel
from goldfxgraph.persistence.repositories import MarketDataRepository
from goldfxgraph.schemas.forecast import DailyBar


def _bar(day: int, close: float, *, source: str = "csv", symbol: str = "XAUUSD") -> DailyBar:
    return DailyBar(
        date=date(2024, 1, day),
        open=close - 3,
        high=close + 2,
        low=close - 5,
        close=close,
        volume=10,
        source=source,
        symbol=symbol,
    )


def test_market_data_bar_model_is_importable() -> None:
    assert MarketDataBarModel.__tablename__ == "market_data_bars"


@pytest.mark.asyncio
async def test_upsert_market_bars_writes_rows_and_returns_latest_bar() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = MarketDataRepository(session_factory)

    written = await repository.upsert_market_bars([_bar(1, 2050), _bar(2, 2058)])

    latest = await repository.get_latest_market_bar("xauusd")
    count = await repository.get_market_bars_count()

    assert written == 2
    assert count == 2
    assert latest is not None
    assert latest.date == date(2024, 1, 2)
    assert latest.close == 2058


@pytest.mark.asyncio
async def test_get_market_bars_between_returns_sorted_range_and_single_day_lookup() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = MarketDataRepository(session_factory)

    await repository.upsert_market_bars([_bar(1, 2050), _bar(2, 2055), _bar(3, 2060)])

    bars = await repository.get_market_bars_between("XAUUSD", date(2024, 1, 2), date(2024, 1, 3))
    target = await repository.get_market_bars_for_date("XAUUSD", date(2024, 1, 3))

    assert [bar.date.isoformat() for bar in bars] == ["2024-01-02", "2024-01-03"]
    assert target is not None
    assert target.date == date(2024, 1, 3)
    assert target.close == 2060


@pytest.mark.asyncio
async def test_get_recent_market_bars_returns_latest_window() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = MarketDataRepository(session_factory)

    await repository.upsert_market_bars([_bar(day, 2050 + day) for day in range(1, 31)])

    bars = await repository.get_recent_market_bars("XAUUSD", limit=20)

    assert len(bars) == 20
    assert [bar.date.isoformat() for bar in bars[:3]] == ["2024-01-11", "2024-01-12", "2024-01-13"]
    assert bars[-1].date == date(2024, 1, 30)
    assert bars[-1].close == 2080


@pytest.mark.asyncio
async def test_upsert_market_bars_is_idempotent_for_same_day_imports() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = MarketDataRepository(session_factory)
    initial_bar = _bar(1, 2050, source="initial")
    updated_bar = _bar(1, 2062, source="updated")

    first_written = await repository.upsert_market_bars([initial_bar])
    second_written = await repository.upsert_market_bars([updated_bar])

    latest = await repository.get_latest_market_bar()
    count = await repository.get_market_bars_count()

    assert first_written == 1
    assert second_written == 1
    assert count == 1
    assert latest is not None
    assert latest.date == date(2024, 1, 1)
    assert latest.source == "updated"
    assert latest.open == 2059
    assert latest.high == 2064
    assert latest.low == 2057
    assert latest.close == 2062
    assert latest.volume == 10


@pytest.mark.asyncio
async def test_upsert_market_bars_chunks_large_imports_without_exceeding_parameters() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = MarketDataRepository(session_factory)

    bars = [_bar((index % 28) + 1, 2050 + index * 0.01, source="bulk") for index in range(0, 3500)]

    written = await repository.upsert_market_bars(bars)
    count = await repository.get_market_bars_count()

    assert written == 28
    assert count == 28


def test_market_data_repository_uses_postgres_upsert_branch() -> None:
    class _FakeDialect:
        name = "postgresql"

    class _FakeBind:
        dialect = _FakeDialect()

    class _FakeSession:
        bind = _FakeBind()

    statement = MarketDataRepository._build_upsert_statement(
        _FakeSession(),
        [
            {
                "symbol": "XAUUSD",
                "bar_date": date(2024, 1, 1),
                "open": 2050,
                "high": 2055,
                "low": 2045,
                "close": 2052,
                "volume": 10,
                "source": "postgres-test",
                "created_at": None,
                "updated_at": None,
            }
        ],
        written_at=datetime.now(UTC),
    )

    compiled = str(statement.compile(dialect=postgresql_dialect()))
    assert "ON CONFLICT" in compiled
    assert "DO UPDATE" in compiled
