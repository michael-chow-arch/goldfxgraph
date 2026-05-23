from __future__ import annotations

from dataclasses import dataclass

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
