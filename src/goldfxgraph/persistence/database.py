from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


@dataclass(frozen=True)
class SessionFactory:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]


def create_session_factory(database_url: str) -> SessionFactory:
    engine = create_async_engine(database_url)
    return SessionFactory(
        engine=engine,
        sessionmaker=async_sessionmaker(engine, expire_on_commit=False),
    )


async def init_models(engine: AsyncEngine) -> None:
    from goldfxgraph.persistence import models as _models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_ensure_forecast_columns)
        await connection.run_sync(_ensure_scheduler_columns)


def _ensure_forecast_columns(connection) -> None:
    inspector = inspect(connection)
    if "forecasts" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("forecasts")}
    required_columns = {
        "market_sentiment_summary": "TEXT",
        "alt_data_summary": "TEXT",
        "window_directions": "JSON",
        "entry_price_low": "FLOAT",
        "entry_price_high": "FLOAT",
    }

    for column_name, column_type in required_columns.items():
        if column_name in existing_columns:
            continue
        connection.execute(text(f'ALTER TABLE forecasts ADD COLUMN "{column_name}" {column_type}'))


def _ensure_scheduler_columns(connection) -> None:
    inspector = inspect(connection)
    if "scheduler_runs" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("scheduler_runs")}
    required_columns = {
        "agent_diagnostics": "JSON",
    }

    for column_name, column_type in required_columns.items():
        if column_name in existing_columns:
            continue
        connection.execute(text(f'ALTER TABLE scheduler_runs ADD COLUMN "{column_name}" {column_type}'))
