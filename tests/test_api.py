from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient
from pydantic import SecretStr

from goldfxgraph.api.app import create_app
from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import AgentVote, ForecastDirection, ForecastResult, ResearchRunResult


class InMemoryForecastRepository:
    def __init__(self) -> None:
        self._next_run_id = 1
        self._next_forecast_id = 1
        self.runs: dict[int, ResearchRunResult] = {}
        self.forecasts: dict[int, ForecastResult] = {}

    async def create_research_run(self, input_summary: dict[str, object]) -> Any:
        run_id = self._next_run_id
        self._next_run_id += 1
        self.runs[run_id] = ResearchRunResult(
            id=run_id,
            status="running",
            started_at=datetime.now(UTC),
            input_summary=dict(input_summary),
        )
        return type("ResearchRunRecord", (), {"id": run_id})()

    async def mark_run_success(self, run_id: int) -> None:
        run = self.runs[run_id]
        self.runs[run_id] = run.model_copy(update={"status": "success", "completed_at": datetime.now(UTC)})

    async def mark_run_failed(self, run_id: int, error_message: str) -> None:
        run = self.runs[run_id]
        self.runs[run_id] = run.model_copy(
            update={"status": "failed", "completed_at": datetime.now(UTC), "error_message": error_message}
        )

    async def save_forecast(self, run_id: int, forecast: ForecastResult) -> ForecastResult:
        saved = forecast.model_copy(update={"id": self._next_forecast_id, "run_id": run_id})
        self._next_forecast_id += 1
        self.forecasts[saved.id or 0] = saved
        self.runs[run_id] = self.runs[run_id].model_copy(update={"forecast": saved})
        return saved

    async def get_latest_forecast(self) -> ForecastResult | None:
        if not self.forecasts:
            return None
        return self.forecasts[max(self.forecasts)]

    async def get_research_run(self, run_id: int) -> ResearchRunResult | None:
        return self.runs.get(run_id)


def test_latest_forecast_returns_empty_when_none_exists() -> None:
    client = TestClient(create_app(testing=True))

    response = client.get("/api/v1/forecast/latest")

    assert response.status_code in {200, 404}
    assert "agent-key" not in response.text


def test_health_endpoint() -> None:
    client = TestClient(create_app(testing=True))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_research_run_returns_structured_error_when_quote_provider_unconfigured(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    repository = InMemoryForecastRepository()
    settings = GoldFXGraphSettings(
        xauusd_csv_path=csv_path,
        current_quote_url=None,
        current_quote_api_key=SecretStr("quote-secret"),
        agent_api_key=SecretStr("agent-key"),
    )
    client = TestClient(create_app(testing=True, settings=settings, repository=cast(ForecastRepository, repository)))

    response = client.post("/api/v1/research-runs")

    assert response.status_code == 503
    assert response.json()["error"]["type"] == "quote_provider_unconfigured"
    assert "agent-key" not in response.text
    assert "quote-secret" not in response.text
    assert repository.runs[1].status == "failed"


def test_get_research_run_returns_structured_404_for_missing_run() -> None:
    client = TestClient(create_app(testing=True, repository=cast(ForecastRepository, InMemoryForecastRepository())))

    response = client.get("/api/v1/research-runs/404")

    assert response.status_code == 404
    assert response.json() == {"error": {"type": "research_run_not_found", "message": "Research run was not found"}}


def test_latest_forecast_returns_seeded_forecast_without_secret_leak() -> None:
    repository = InMemoryForecastRepository()
    forecast = _forecast()
    repository.forecasts[1] = forecast
    settings = GoldFXGraphSettings(agent_api_key=SecretStr("agent-key"))
    client = TestClient(create_app(testing=True, settings=settings, repository=cast(ForecastRepository, repository)))

    response = client.get("/api/v1/forecast/latest")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "XAUUSD"
    assert body["direction"] == "bullish"
    assert body["agent_votes"][0]["agent"] == "technical"
    assert "agent-key" not in response.text


def _forecast() -> ForecastResult:
    now = datetime.now(UTC)
    return ForecastResult(
        id=1,
        run_id=1,
        reference_time=now,
        data_timestamp=now,
        data_source="unit-test",
        current_price=2050.25,
        daily_open=2040,
        daily_high=2060,
        daily_low=2030,
        daily_close=2048,
        direction=ForecastDirection.bullish,
        entry_price=2050.25,
        take_profit_price=2080,
        stop_loss_price=2035,
        holding_period="1-3 个交易日",
        intraday_action="仅用于研究观察",
        long_term_action="继续观察日线确认",
        confidence_score=0.64,
        technical_summary="技术面偏多",
        macro_summary="宏观面中性",
        news_summary="新闻面中性",
        risk_summary="波动风险可控",
        agent_votes=[
            AgentVote(
                agent="technical",
                direction=ForecastDirection.bullish,
                confidence=0.7,
                rationale="趋势偏多",
            )
        ],
        risk_notes=["仅供研究"],
    )


def _write_csv(tmp_path: Path) -> Path:
    path = tmp_path / "xauusd_daily.csv"
    path.write_text(
        "\n".join(
            [
                "date,open,high,low,close,source,symbol",
                "2024-01-01,2040,2050,2030,2045,unit,XAUUSD",
                "2024-01-02,2045,2060,2040,2055,unit,XAUUSD",
            ]
        ),
        encoding="utf-8",
    )
    return path
