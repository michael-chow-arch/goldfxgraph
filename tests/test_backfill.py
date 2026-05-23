from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import SecretStr

from goldfxgraph.backfill.cli import main as backfill_main
from goldfxgraph.backfill.eod_backfill import BackfillValidationError, run_eod_backfill
from goldfxgraph.cli import main as goldfxgraph_main
from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.schemas.forecast import ForecastDirection


class _FakeAgentResult:
    def __init__(self, summary: str) -> None:
        self.summary = summary
        self.direction = ForecastDirection.neutral
        self.confidence = 0.72
        self.risk_notes = []


class _FakeAgentClient:
    def __init__(self, summaries: list[str]) -> None:
        self._summaries = summaries
        self.calls: list[tuple[str, dict[str, object]]] = []

    def invoke_agent(self, agent_name: str, payload: dict[str, object]) -> _FakeAgentResult:
        self.calls.append((agent_name, payload))
        if not self._summaries:
            raise AssertionError("unexpected extra backfill agent call")
        return _FakeAgentResult(self._summaries.pop(0))


def _write_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "xauusd_daily.csv"
    csv_path.write_text(
        "date,open,high,low,close,source,symbol\n"
        "2024-01-05,2045,2060,2038,2055,unit-feed,XAUUSD\n",
        encoding="utf-8",
    )
    return csv_path


def _settings(csv_path: Path) -> GoldFXGraphSettings:
    return GoldFXGraphSettings(
        xauusd_csv_path=csv_path,
        openai_base_url="https://agent.example.test/v1",
        openai_model="gpt-4.1-mini",
        openai_api_key=SecretStr("agent-secret"),
        eod_backfill_timezone="America/New_York",
        eod_backfill_cutoff_hour=17,
        eod_backfill_cutoff_minute=0,
    )


def test_compute_missing_completed_trading_days_respects_us_eastern_cutoff(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    settings = _settings(csv_path)
    agent = _FakeAgentClient([])

    before_close = datetime(2024, 1, 8, 16, 59, tzinfo=ZoneInfo("America/New_York"))
    after_close = datetime(2024, 1, 8, 17, 1, tzinfo=ZoneInfo("America/New_York"))

    before_result = run_eod_backfill(settings=settings, agent_client=agent, now=before_close)
    after_result = run_eod_backfill(
        settings=settings,
        agent_client=_FakeAgentClient(
            [
                json.dumps(
                    {
                        "date": "2024-01-08",
                        "open": 2056.0,
                        "high": 2064.0,
                        "low": 2048.0,
                        "close": 2059.0,
                        "source": "unit-backfill-agent",
                        "symbol": "XAUUSD",
                        "confidence": 0.81,
                    }
                )
            ]
        ),
        now=after_close,
    )

    assert before_result.missing_dates == []
    assert before_result.written is False
    assert after_result.missing_dates == [date(2024, 1, 8)]
    assert after_result.written is True


def test_run_eod_backfill_appends_missing_bars_atomically(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    original_text = csv_path.read_text(encoding="utf-8")
    settings = _settings(csv_path)
    agent = _FakeAgentClient(
        [
            json.dumps(
                {
                    "date": "2024-01-08",
                    "open": 2056.0,
                    "high": 2064.0,
                    "low": 2048.0,
                    "close": 2059.0,
                    "source": "unit-backfill-agent",
                    "symbol": "XAUUSD",
                    "confidence": 0.81,
                }
            )
        ]
    )

    result = run_eod_backfill(
        settings=settings,
        agent_client=agent,
        now=datetime(2024, 1, 8, 17, 1, tzinfo=ZoneInfo("America/New_York")),
    )

    rewritten = csv_path.read_text(encoding="utf-8")

    assert result.appended_dates == [date(2024, 1, 8)]
    assert "2024-01-08" in rewritten
    assert rewritten != original_text
    assert "unit-backfill-agent" in rewritten


def test_run_eod_backfill_keeps_original_csv_when_candidate_validation_fails(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    original_text = csv_path.read_text(encoding="utf-8")
    settings = _settings(csv_path)
    agent = _FakeAgentClient(
        [
            json.dumps(
                {
                    "date": "2024-01-08",
                    "open": 2056.0,
                    "high": 2040.0,
                    "low": 2048.0,
                    "close": 2059.0,
                    "source": "unit-backfill-agent",
                    "symbol": "XAUUSD",
                    "confidence": 0.81,
                }
            )
        ]
    )

    with pytest.raises(BackfillValidationError, match="high must be greater than or equal to low"):
        run_eod_backfill(
            settings=settings,
            agent_client=agent,
            now=datetime(2024, 1, 8, 17, 1, tzinfo=ZoneInfo("America/New_York")),
        )

    assert csv_path.read_text(encoding="utf-8") == original_text


def test_goldfxgraph_cli_dispatches_backfill_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv_path = _write_csv(tmp_path)
    captured: dict[str, object] = {}

    def fake_run_eod_backfill(**kwargs: object) -> object:
        captured.update(kwargs)
        return type(
            "Result",
            (),
            {
                "csv_path": csv_path,
                "written": False,
                "missing_dates": [],
                "appended_dates": [],
                "latest_existing_date": date(2024, 1, 5),
            },
        )()

    monkeypatch.setattr("goldfxgraph.backfill.cli.run_eod_backfill", fake_run_eod_backfill)

    exit_code = goldfxgraph_main(
        [
            "backfill",
            "--csv-path",
            str(csv_path),
            "--as-of",
            "2024-01-08T17:01:00-05:00",
        ]
    )

    assert exit_code == 0
    assert captured["csv_path"] == csv_path
    assert isinstance(captured["settings"], GoldFXGraphSettings)
    assert isinstance(captured["now"], datetime)


def test_backfill_cli_module_can_run_directly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv_path = _write_csv(tmp_path)
    captured: dict[str, object] = {}

    def fake_run_eod_backfill(**kwargs: object) -> object:
        captured.update(kwargs)
        return type(
            "Result",
            (),
            {
                "csv_path": csv_path,
                "written": False,
                "missing_dates": [],
                "appended_dates": [],
                "latest_existing_date": date(2024, 1, 5),
            },
        )()

    monkeypatch.setattr("goldfxgraph.backfill.cli.run_eod_backfill", fake_run_eod_backfill)

    exit_code = backfill_main(
        [
            "--csv-path",
            str(csv_path),
            "--as-of",
            "2024-01-08T17:01:00-05:00",
        ]
    )

    assert exit_code == 0
    assert captured["csv_path"] == csv_path
    assert isinstance(captured["settings"], GoldFXGraphSettings)
    assert isinstance(captured["now"], datetime)
