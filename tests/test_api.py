from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient
from pydantic import SecretStr
from starlette.exceptions import HTTPException as StarletteHTTPException

from goldfxgraph.api import routes
from goldfxgraph.api.app import create_app
from goldfxgraph.llm.openai_client import OpenAIAgentClient, OpenAIClientError
from goldfxgraph.market_data.current_quote import QuoteProviderError
from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import AgentVote, CurrentQuote, ForecastDirection, ForecastResult, ResearchRunResult
from goldfxgraph.workflow import nodes


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


def test_api_allows_local_frontend_origin_via_cors() -> None:
    client = TestClient(create_app(testing=True))

    response = client.options(
        "/api/v1/forecast/latest",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unknown_api_route_returns_structured_404() -> None:
    client = TestClient(create_app(testing=True))

    response = client.get("/api/v1/unknown")

    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found"
    assert "detail" not in response.json()


def test_path_validation_returns_structured_422() -> None:
    client = TestClient(create_app(testing=True))

    response = client.get("/api/v1/research-runs/not-an-int")

    assert response.status_code == 422
    assert response.json()["error"]["type"] == "validation_error"
    assert "detail" not in response.json()


def test_http_exception_detail_is_not_leaked() -> None:
    app = create_app(testing=True)

    @app.get("/api/v1/leaky")
    async def leaky_route() -> None:
        raise StarletteHTTPException(status_code=409, detail="internal-secret-token")

    client = TestClient(app)

    response = client.get("/api/v1/leaky")

    assert response.status_code == 409
    assert response.json() == {"error": {"type": "http_error", "message": "HTTP request failed"}}
    assert "internal-secret-token" not in response.text


def test_create_research_run_succeeds_without_manual_quote_url_when_discovery_succeeds(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    csv_path = _write_csv(tmp_path)
    repository = InMemoryForecastRepository()
    monkeypatch.setattr(
        nodes.CurrentQuoteProvider,
        "fetch",
        lambda self: CurrentQuote(
            symbol="XAUUSD",
            current_price=2058.0,
            data_source="discovered-provider",
            data_timestamp=datetime.now(UTC),
        ),
    )
    settings = GoldFXGraphSettings(
        xauusd_csv_path=csv_path,
        current_quote_url=None,
        current_quote_api_key=SecretStr("quote-secret"),
        openai_api_key=SecretStr("agent-key"),
    )
    client = TestClient(create_app(testing=True, settings=settings, repository=cast(ForecastRepository, repository)))

    response = client.post("/api/v1/research-runs")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["forecast"]["data_source"] == "discovered-provider"
    assert "agent-key" not in response.text
    assert "quote-secret" not in response.text
    assert repository.runs[1].status == "success"


def test_create_research_run_surfaces_remote_agent_fallback_in_forecast(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    csv_path = _write_csv(tmp_path)
    repository = InMemoryForecastRepository()
    monkeypatch.setattr(
        nodes.CurrentQuoteProvider,
        "fetch",
        lambda self: CurrentQuote(
            symbol="XAUUSD",
            current_price=2058.0,
            data_source="discovered-provider",
            data_timestamp=datetime.now(UTC),
        ),
    )
    monkeypatch.setattr(
        OpenAIAgentClient,
        "invoke_agent",
        lambda self, agent_name, payload: (_ for _ in ()).throw(OpenAIClientError(f"{agent_name} failed")),
    )
    settings = GoldFXGraphSettings(
        xauusd_csv_path=csv_path,
        openai_base_url="https://agent.example.test/v1",
        openai_model="gpt-4.1-mini",
        openai_api_key=SecretStr("agent-key"),
    )
    client = TestClient(create_app(testing=True, settings=settings, repository=cast(ForecastRepository, repository)))

    response = client.post("/api/v1/research-runs")

    assert response.status_code == 200
    notes = response.json()["forecast"]["risk_notes"]
    assert any("OpenAI-compatible technical agent 调用失败" in note for note in notes)
    assert any("OpenAI-compatible macro agent 调用失败" in note for note in notes)


def test_create_research_run_uses_cached_langgraph_workflow(monkeypatch: Any) -> None:
    repository = InMemoryForecastRepository()
    compile_count = 0
    invoke_count = 0

    class FakeCompiledGraph:
        async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
            nonlocal invoke_count
            invoke_count += 1
            forecast = _forecast()
            saved = await state["repository"].save_forecast(state["run_id"], forecast)
            await state["repository"].mark_run_success(state["run_id"])
            return {**state, "result": saved, "forecast": saved}

    class FakeGraph:
        def compile(self) -> FakeCompiledGraph:
            nonlocal compile_count
            compile_count += 1
            return FakeCompiledGraph()

    monkeypatch.setattr(routes, "build_forecast_graph", lambda: FakeGraph())
    client = TestClient(create_app(testing=True, repository=cast(ForecastRepository, repository)))

    response = client.post("/api/v1/research-runs")
    second_response = client.post("/api/v1/research-runs")

    assert response.status_code == 200
    assert second_response.status_code == 200
    assert compile_count == 1
    assert invoke_count == 2
    assert response.json()["status"] == "success"
    assert response.json()["forecast"]["direction"] == "bullish"


def test_invalid_workflow_terminal_state_marks_run_failed(monkeypatch: Any) -> None:
    repository = InMemoryForecastRepository()

    class FakeCompiledGraph:
        async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
            return {**state, "result": None, "forecast": None}

    class FakeGraph:
        def compile(self) -> FakeCompiledGraph:
            return FakeCompiledGraph()

    monkeypatch.setattr(routes, "build_forecast_graph", lambda: FakeGraph())
    client = TestClient(create_app(testing=True, repository=cast(ForecastRepository, repository)))

    response = client.post("/api/v1/research-runs")

    assert response.status_code == 502
    assert response.json()["error"]["type"] == "workflow_error"
    assert repository.runs[1].status == "failed"
    assert repository.runs[1].error_message == "Workflow did not produce a forecast result"


def test_configured_quote_provider_failure_records_sanitized_error(tmp_path: Path) -> None:
    repository = InMemoryForecastRepository()
    settings = GoldFXGraphSettings(
        xauusd_csv_path=_write_csv(tmp_path),
        current_quote_url="not-a-valid-url",
        current_quote_api_key=SecretStr("quote-secret"),
    )
    original_fetch = nodes.CurrentQuoteProvider.fetch

    def failing_fetch(self: Any) -> Any:
        raise QuoteProviderError("Current quote discovery failed")

    nodes.CurrentQuoteProvider.fetch = failing_fetch
    client = TestClient(create_app(testing=True, settings=settings, repository=cast(ForecastRepository, repository)))

    try:
        response = client.post("/api/v1/research-runs")
    finally:
        nodes.CurrentQuoteProvider.fetch = original_fetch

    assert response.status_code == 503
    assert response.json()["error"]["type"] == "quote_provider_error"
    assert repository.runs[1].status == "failed"
    assert repository.runs[1].error_message == "Current quote discovery failed"
    assert "quote-secret" not in response.text
    assert "quote-secret" not in str(repository.runs[1].error_message)


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
