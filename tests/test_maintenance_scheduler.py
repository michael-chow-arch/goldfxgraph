from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import SecretStr

from goldfxgraph.backfill.maintenance import run_eod_maintenance
from goldfxgraph.backfill.scheduler import calculate_next_run_at, run_eod_maintenance_loop
from goldfxgraph.packages.common.settings import GoldFXGraphSettings


def _settings() -> GoldFXGraphSettings:
    return GoldFXGraphSettings(
        xauusd_csv_path="data/raw/xauusd_daily.csv",
        openai_api_key=SecretStr("test"),
        eod_backfill_timezone="America/New_York",
        eod_backfill_cutoff_hour=17,
        eod_backfill_cutoff_minute=0,
    )


@pytest.mark.asyncio
async def test_run_eod_maintenance_runs_backfill_before_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_backfill(**kwargs: object) -> object:
        calls.append("backfill")
        return type("BackfillResult", (), {"written": True, "status": "written"})()

    async def fake_evaluation(**kwargs: object) -> object:
        calls.append("evaluation")
        return type("EvaluationResult", (), {"written": True, "status": "written"})()

    monkeypatch.setattr("goldfxgraph.backfill.maintenance.run_eod_backfill", fake_backfill)
    monkeypatch.setattr("goldfxgraph.backfill.maintenance.run_eod_forecast_evaluation", fake_evaluation)

    result = await run_eod_maintenance(
        settings=_settings(),
        repository=object(),
        now=datetime(2024, 1, 5, 22, 30, tzinfo=UTC),
    )  # type: ignore[arg-type]

    assert calls == ["backfill", "evaluation"]
    assert result.status == "written"
    assert result.wrote_anything is True


@pytest.mark.asyncio
async def test_run_eod_maintenance_returns_failed_when_backfill_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_backfill(**kwargs: object) -> object:
        return type(
            "BackfillResult",
            (),
            {
                "written": False,
                "status": "failed",
                "failed": True,
                "failure_reason": "history source unavailable",
            },
        )()

    async def fake_evaluation(**kwargs: object) -> object:
        return type("EvaluationResult", (), {"written": False, "status": "no-op"})()

    monkeypatch.setattr("goldfxgraph.backfill.maintenance.run_eod_backfill", fake_backfill)
    monkeypatch.setattr("goldfxgraph.backfill.maintenance.run_eod_forecast_evaluation", fake_evaluation)

    result = await run_eod_maintenance(
        settings=_settings(),
        repository=object(),
        now=datetime(2024, 1, 5, 22, 30, tzinfo=UTC),
    )  # type: ignore[arg-type]

    assert result.status == "failed"
    assert result.backfill.failed is True
    assert result.wrote_anything is False


def test_calculate_next_run_at_skips_saturday_and_cutoff() -> None:
    next_run = calculate_next_run_at(
        now=datetime(2024, 1, 5, 18, 30, tzinfo=ZoneInfo("America/New_York")),
        timezone_name="America/New_York",
        cutoff_hour=17,
        cutoff_minute=0,
    )

    local_next_run = next_run.astimezone(ZoneInfo("America/New_York"))
    assert local_next_run.date().isoformat() == "2024-01-07"
    assert local_next_run.hour == 17
    assert local_next_run.minute == 0


@pytest.mark.asyncio
async def test_run_eod_maintenance_loop_runs_once_immediately_on_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    stop_event = asyncio.Event()

    async def fake_maintenance(**kwargs: object) -> object:
        calls.append("maintenance")
        stop_event.set()
        target_date = datetime(2024, 1, 5, 0, 0, tzinfo=UTC).date()
        backfill_result = type(
            "Backfill",
            (),
            {
                "status": "no-op",
                "latest_existing_date": None,
                "target_date": target_date,
                "missing_dates": [],
            },
        )()
        return type(
            "Result",
            (),
            {
                "status": "no-op",
                "backfill": backfill_result,
                "evaluation": type("Evaluation", (), {"status": "no-op"})(),
            },
        )()

    monkeypatch.setattr("goldfxgraph.backfill.scheduler.run_eod_maintenance", fake_maintenance)

    await run_eod_maintenance_loop(
        settings=_settings(),
        repository=object(),
        stop_event=stop_event,
    )  # type: ignore[arg-type]

    assert calls == ["maintenance"]


@pytest.mark.asyncio
async def test_scheduler_logs_error_when_maintenance_fails(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    stop_event = asyncio.Event()

    async def fake_maintenance(**kwargs: object) -> object:
        stop_event.set()
        backfill_result = type(
            "Backfill",
            (),
            {
                "status": "failed",
                "written": False,
                "failed": True,
                "latest_existing_date": datetime(2024, 1, 5, 0, 0, tzinfo=UTC).date(),
                "target_date": datetime(2024, 1, 8, 0, 0, tzinfo=UTC).date(),
                "missing_dates": [datetime(2024, 1, 8, 0, 0, tzinfo=UTC).date()],
                "failure_reason": "history source unavailable",
            },
        )()
        return type(
            "Result",
            (),
            {
                "status": "failed",
                "backfill": backfill_result,
                "evaluation": type("Evaluation", (), {"status": "no-op"})(),
            },
        )()

    monkeypatch.setattr("goldfxgraph.backfill.scheduler.run_eod_maintenance", fake_maintenance)

    with caplog.at_level("ERROR"):
        await run_eod_maintenance_loop(
            settings=_settings(),
            repository=object(),
            stop_event=stop_event,
        )  # type: ignore[arg-type]

    assert any(record.levelname == "ERROR" and "eod maintenance failed" in record.message for record in caplog.records)
