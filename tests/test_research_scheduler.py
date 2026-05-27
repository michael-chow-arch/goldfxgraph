from __future__ import annotations

import pytest
from pydantic import SecretStr

from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.research.scheduler import build_research_scheduler


def _settings() -> GoldFXGraphSettings:
    return GoldFXGraphSettings(
        xauusd_csv_path="data/raw/xauusd_daily.csv",
        openai_api_key=SecretStr("test"),
    )


@pytest.mark.asyncio
async def test_research_scheduler_run_once_updates_status_and_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = ForecastRepository(session_factory)
    scheduler = build_research_scheduler(
        settings=_settings(),
        repository=repository,
        interval_seconds=1,
    )

    async def fake_run_forecast_workflow(**kwargs: object) -> object:
        assert kwargs["scheduler_run_id"] is not None
        run = await repository.get_research_run(int(kwargs["run_id"]))
        assert run is not None
        return {
            "result": object(),
            "agent_diagnostics": [
                {
                    "agent": "technical",
                    "stage": "agent_technical_analysis",
                    "status": "failed",
                    "message": "OpenAI-compatible technical agent 调用失败，已回退到 deterministic workflow 输出。",
                    "detail": "HTTP 500: upstream unavailable",
                }
            ],
        }

    monkeypatch.setattr("goldfxgraph.research.scheduler.run_forecast_workflow", fake_run_forecast_workflow)

    status = await scheduler.run_once()

    assert status.status == "success"
    assert status.current_stage == "persist_result"
    assert status.completed_at is not None
    assert scheduler.latest_status is not None
    assert scheduler.latest_status.status == "success"
    assert all(item["status"] == "success" for item in status.agent_statuses)
    assert status.agent_diagnostics[0]["detail"] == "HTTP 500: upstream unavailable"


@pytest.mark.asyncio
async def test_research_scheduler_run_once_marks_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = ForecastRepository(session_factory)
    scheduler = build_research_scheduler(
        settings=_settings(),
        repository=repository,
        interval_seconds=1,
    )

    async def fake_run_forecast_workflow(**kwargs: object) -> object:
        raise RuntimeError("scheduler boom")

    monkeypatch.setattr("goldfxgraph.research.scheduler.run_forecast_workflow", fake_run_forecast_workflow)

    status = await scheduler.run_once()

    assert status.status == "failed"
    assert status.current_stage == "failed"
    assert status.last_error == "scheduler boom"
    assert scheduler.latest_status is not None
    assert scheduler.latest_status.status == "failed"
