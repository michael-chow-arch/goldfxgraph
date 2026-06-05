from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select

from goldfxgraph.persistence.database import SessionFactory
from goldfxgraph.persistence.models import ExternalSourceModel


class ExternalSourceNotFoundError(LookupError):
    def __init__(self, source_key: str) -> None:
        self.source_key = source_key
        super().__init__(f"active external source not found for source_key={source_key!r}")


@dataclass(frozen=True, slots=True)
class ExternalSourceSnapshot:
    id: int
    source_key: str
    source_type: str
    endpoint_url: str
    request_config: dict[str, Any]
    version: str
    is_active: bool
    description: str | None
    change_notes: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def headers(self) -> dict[str, str]:
        headers = self.request_config.get("headers")
        if isinstance(headers, Mapping):
            return {str(key): str(value) for key, value in headers.items()}
        return {}

    @property
    def params(self) -> dict[str, str]:
        params = self.request_config.get("params")
        if isinstance(params, Mapping):
            return {str(key): str(value) for key, value in params.items()}
        return {}

    @property
    def model(self) -> str | None:
        value = self.request_config.get("model")
        if value is None:
            return None
        rendered = str(value).strip()
        return rendered or None

    @property
    def api_key(self) -> str | None:
        value = self.request_config.get("api_key")
        if value is None:
            return None
        rendered = str(value).strip()
        return rendered or None

    @property
    def timeout(self) -> float | None:
        value = self.request_config.get("timeout")
        if value is None:
            return None
        try:
            rendered = float(value)
        except (TypeError, ValueError):
            return None
        return rendered if rendered > 0 else None


class ExternalSourceRegistryService:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def get_active_source(self, source_key: str) -> ExternalSourceSnapshot:
        normalized_source_key = _normalize_source_key(source_key)
        async with self._session_factory.sessionmaker() as session:
            statement = (
                select(ExternalSourceModel)
                .where(
                    ExternalSourceModel.source_key == normalized_source_key,
                    ExternalSourceModel.is_active.is_(True),
                )
                .order_by(ExternalSourceModel.updated_at.desc(), ExternalSourceModel.id.desc())
                .limit(1)
            )
            result = await session.execute(statement)
            model = result.scalars().first()
            if model is None:
                raise ExternalSourceNotFoundError(normalized_source_key)
            return _snapshot_from_model(model)

    async def get_active_sources(self, source_keys: list[str]) -> dict[str, ExternalSourceSnapshot]:
        sources: dict[str, ExternalSourceSnapshot] = {}
        for source_key in source_keys:
            sources[source_key] = await self.get_active_source(source_key)
        return sources


def _snapshot_from_model(model: ExternalSourceModel) -> ExternalSourceSnapshot:
    return ExternalSourceSnapshot(
        id=model.id,
        source_key=model.source_key,
        source_type=model.source_type,
        endpoint_url=model.endpoint_url,
        request_config=dict(model.request_config),
        version=model.version,
        is_active=model.is_active,
        description=model.description,
        change_notes=model.change_notes,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _normalize_source_key(source_key: str) -> str:
    normalized_source_key = source_key.strip()
    if not normalized_source_key:
        raise ValueError("source_key must not be empty")
    return normalized_source_key
