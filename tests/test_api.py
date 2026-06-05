from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from starlette.exceptions import HTTPException as StarletteHTTPException

from goldfxgraph.api.app import create_app
from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.models import PromptTemplateModel
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import (
    Actionability,
    AgentVote,
    DailyBar,
    FinalBias,
    FinalForecast,
    ForecastDirection,
    ForecastResult,
    ForecastWindowDirection,
    PromptVersionMetadata,
    ResearchRunResult,
    SchedulerRunStatus,
)
from conftest import seed_runtime_registry


class InMemoryForecastRepository:
    def __init__(self) -> None:
        self._next_run_id = 1
        self._next_forecast_id = 1
        self._next_scheduler_run_id = 1
        self.runs: dict[int, ResearchRunResult] = {}
        self.forecasts: dict[int, ForecastResult] = {}
        self.scheduler_runs: dict[int, SchedulerRunStatus] = {}
        self.market_bars: dict[tuple[str, date], DailyBar] = {}

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

    async def create_scheduler_run(self, input_summary: dict[str, object]) -> Any:
        run_id = self._next_scheduler_run_id
        self._next_scheduler_run_id += 1
        self.scheduler_runs[run_id] = SchedulerRunStatus(
            id=run_id,
            status="running",
            started_at=datetime.now(UTC),
            current_stage="scheduled",
            agent_statuses=[],
            agent_diagnostics=[],
            last_error=None,
        )
        return type("SchedulerRunRecord", (), {"id": run_id})()

    async def update_scheduler_run_stage(
        self,
        run_id: int,
        *,
        current_stage: str,
        agent_statuses: list[dict[str, str]] | None = None,
        agent_diagnostics: list[dict[str, Any]] | None = None,
        status: str = "running",
        last_error: str | None = None,
        completed_at: datetime | None = None,
    ) -> SchedulerRunStatus:
        run = self.scheduler_runs[run_id]
        updated = run.model_copy(
            update={
                "status": status,
                "current_stage": current_stage,
                "agent_statuses": list(agent_statuses or []),
                "agent_diagnostics": list(agent_diagnostics or []),
                "last_error": last_error,
                "completed_at": completed_at,
            }
        )
        self.scheduler_runs[run_id] = updated
        return updated

    async def get_latest_scheduler_run(self) -> SchedulerRunStatus | None:
        if not self.scheduler_runs:
            return None
        return self.scheduler_runs[max(self.scheduler_runs)]

    async def upsert_market_bars(self, bars: list[DailyBar]) -> int:
        for bar in bars:
            self.market_bars[(bar.symbol.upper(), bar.date)] = bar
        return len(bars)

    async def get_latest_market_bar(self, symbol: str = "XAUUSD") -> DailyBar | None:
        symbol_key = symbol.strip().upper()
        bars = [bar for (bar_symbol, _), bar in self.market_bars.items() if bar_symbol == symbol_key]
        return max(bars, key=lambda bar: (bar.date, bar.symbol), default=None)

    async def get_market_bars_between(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[DailyBar]:
        symbol_key = symbol.strip().upper()
        bars = [
            bar
            for (bar_symbol, bar_date), bar in self.market_bars.items()
            if bar_symbol == symbol_key and start_date <= bar_date <= end_date
        ]
        return sorted(bars, key=lambda bar: (bar.date, bar.symbol))

    async def get_recent_market_bars(self, symbol: str = "XAUUSD", limit: int = 60) -> list[DailyBar]:
        symbol_key = symbol.strip().upper()
        bars = [bar for (bar_symbol, _), bar in self.market_bars.items() if bar_symbol == symbol_key]
        sorted_bars = sorted(bars, key=lambda bar: (bar.date, bar.symbol))
        return sorted_bars[-max(1, min(int(limit), 180)) :]

    async def get_market_bars_for_date(self, symbol: str, target_date: date) -> DailyBar | None:
        return self.market_bars.get((symbol.strip().upper(), target_date))

    async def get_market_bars_count(self, symbol: str = "XAUUSD") -> int:
        symbol_key = symbol.strip().upper()
        return sum(1 for (bar_symbol, _) in self.market_bars if bar_symbol == symbol_key)

    async def get_latest_forecast(self) -> ForecastResult | None:
        if not self.forecasts:
            return None
        return self.forecasts[max(self.forecasts)]

    async def get_forecast_history(self, limit: int = 50) -> list[Any]:
        return []

    async def get_latest_evaluation_summary(self, limit: int = 5) -> list[str]:
        return []

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


def test_startup_registers_research_scheduler(monkeypatch: Any, tmp_path: Path) -> None:
    from goldfxgraph.research.scheduler import ResearchSchedulerHandle

    repository = InMemoryForecastRepository()
    scheduler_task: asyncio.Task[None] | None = None

    async def fake_health_check(**kwargs: Any) -> Any:
        return type("HealthReport", (), {"status": "ok"})()

    def fake_start_research_scheduler(**kwargs: Any) -> ResearchSchedulerHandle:
        nonlocal scheduler_task
        scheduler_task = asyncio.create_task(asyncio.sleep(3600))
        return ResearchSchedulerHandle(
            stop_event=asyncio.Event(),
            task=scheduler_task,
            scheduler=type("Scheduler", (), {"latest_status": None})(),
        )

    monkeypatch.setattr("goldfxgraph.api.app.run_agent_health_check", fake_health_check)
    monkeypatch.setattr("goldfxgraph.api.app.start_research_scheduler", fake_start_research_scheduler)

    db_path = tmp_path / "scheduler-startup.sqlite3"
    settings = GoldFXGraphSettings(
        xauusd_csv_path=tmp_path / "unused.csv",
        database_url=f"sqlite+aiosqlite:///{db_path}",
    )

    async def _seed_database() -> None:
        session_factory = create_session_factory(settings.database_url)
        await init_models(session_factory.engine)
        await seed_runtime_registry(session_factory)
        await session_factory.engine.dispose()

    asyncio.run(_seed_database())

    with TestClient(
        create_app(testing=False, settings=settings, repository=cast(ForecastRepository, repository))
    ) as client:
        assert client.app.state.research_scheduler is not None
        assert client.app.state.research_scheduler.latest_status is None

    assert scheduler_task is not None
    assert scheduler_task.cancelled()


def test_startup_validates_seeded_registry(monkeypatch: Any, tmp_path: Path) -> None:
    from goldfxgraph.research.scheduler import ResearchSchedulerHandle

    scheduler_task: asyncio.Task[None] | None = None

    async def fake_health_check(**kwargs: Any) -> Any:
        return type("HealthReport", (), {"status": "ok"})()

    def fake_start_research_scheduler(**kwargs: Any) -> ResearchSchedulerHandle:
        nonlocal scheduler_task
        scheduler_task = asyncio.create_task(asyncio.sleep(3600))
        return ResearchSchedulerHandle(
            stop_event=asyncio.Event(),
            task=scheduler_task,
            scheduler=type("Scheduler", (), {"latest_status": None})(),
        )

    monkeypatch.setattr("goldfxgraph.api.app.run_agent_health_check", fake_health_check)
    monkeypatch.setattr("goldfxgraph.api.app.start_research_scheduler", fake_start_research_scheduler)

    db_path = tmp_path / "committee-prompts.sqlite3"
    settings = GoldFXGraphSettings(
        xauusd_csv_path=tmp_path / "unused.csv",
        database_url=f"sqlite+aiosqlite:///{db_path}",
    )

    async def _seed_database() -> None:
        session_factory = create_session_factory(settings.database_url)
        await init_models(session_factory.engine)
        await seed_runtime_registry(session_factory)
        await session_factory.engine.dispose()

    asyncio.run(_seed_database())

    with TestClient(create_app(testing=False, settings=settings)) as client:
        session_factory = client.app.state.session_factory
        assert session_factory is not None

        async def _count_prompt_templates() -> int:
            async with session_factory.sessionmaker() as session:
                result = await session.execute(
                    select(func.count()).select_from(PromptTemplateModel).where(
                        PromptTemplateModel.prompt_key == "trading_committee.chair.system"
                    )
                )
                return int(result.scalar_one())

        prompt_count = asyncio.run(_count_prompt_templates())

    assert prompt_count == 1
    assert scheduler_task is not None
    assert scheduler_task.cancelled()


def test_get_market_data_bars_endpoint_returns_recent_daily_bars() -> None:
    repository = InMemoryForecastRepository()
    _seed_market_data(repository)
    client = TestClient(create_app(testing=True, repository=cast(ForecastRepository, repository)))

    response = client.get("/api/v1/market-data/bars?symbol=XAUUSD&limit=3")

    assert response.status_code == 200
    bars = response.json()
    assert len(bars) == 3
    assert [bar["date"] for bar in bars] == ["2024-01-04", "2024-01-05", "2024-01-08"]
    assert bars[-1]["close"] == 2068


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


def test_latest_research_status_returns_empty_when_none_exists() -> None:
    client = TestClient(create_app(testing=True))

    response = client.get("/api/v1/research-status/latest")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"type": "research_status_not_found", "message": "Research status was not found"}
    }


def test_latest_research_status_returns_seeded_status_without_secret_leak() -> None:
    repository = InMemoryForecastRepository()
    repository.scheduler_runs[1] = SchedulerRunStatus(
        id=1,
        status="running",
        started_at=datetime.now(UTC),
        current_stage="agent_technical_analysis",
        agent_statuses=[
            {"agent": "technical", "status": "running"},
            {"agent": "macro", "status": "pending"},
        ],
        last_error=None,
    )
    settings = GoldFXGraphSettings(agent_api_key=SecretStr("agent-key"))
    client = TestClient(create_app(testing=True, settings=settings, repository=cast(ForecastRepository, repository)))

    response = client.get("/api/v1/research-status/latest")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["current_stage"] == "agent_technical_analysis"
    assert body["agent_statuses"][0]["status"] == "running"
    assert "agent-key" not in response.text


def test_manual_research_run_endpoint_is_not_exposed() -> None:
    client = TestClient(create_app(testing=True))

    response = client.post("/api/v1/research-runs")

    assert response.status_code in {404, 405}


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
    assert body["data_source"] == "TradingView"
    assert body["direction"] == "bullish"
    assert body["agent_votes"][0]["agent"] == "technical"
    assert "agent-key" not in response.text


def test_latest_forecast_exposes_committee_metadata_when_available() -> None:
    repository = InMemoryForecastRepository()
    repository.forecasts[1] = _committee_forecast()
    client = TestClient(create_app(testing=True, repository=cast(ForecastRepository, repository)))

    response = client.get("/api/v1/forecast/latest")

    assert response.status_code == 200
    body = response.json()
    assert body["final_bias"] == "bullish"
    assert body["actionability"] == "trade_candidate"
    assert body["prompt_versions"][0]["prompt_key"] == "trading_committee.chair.system"
    assert "committee_decision" in body
    assert "validation_status" in body


def test_research_run_response_exposes_committee_forecast_metadata() -> None:
    repository = InMemoryForecastRepository()
    run_id = 7
    repository.runs[run_id] = ResearchRunResult(
        id=run_id,
        status="success",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        input_summary={"symbol": "XAUUSD"},
        forecast=_committee_forecast(),
    )
    client = TestClient(create_app(testing=True, repository=cast(ForecastRepository, repository)))

    response = client.get(f"/api/v1/research-runs/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["forecast"]["final_bias"] == "bullish"
    assert body["forecast"]["actionability"] == "trade_candidate"
    assert body["forecast"]["prompt_versions"][0]["prompt_key"] == "trading_committee.chair.system"


def _forecast() -> ForecastResult:
    now = datetime.now(UTC)
    return ForecastResult(
        id=1,
        run_id=1,
        reference_time=now,
        data_timestamp=now,
        data_source="TradingView",
        current_price=2050.25,
        daily_open=2040,
        daily_high=2060,
        daily_low=2030,
        daily_close=2048,
        direction=ForecastDirection.bullish,
        window_directions=[
            ForecastWindowDirection(
                window_label="0-3天",
                direction=ForecastDirection.bullish,
                strength="moderate",
                confidence=0.65,
                reason="短期动量延续",
            )
        ],
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


def _committee_forecast() -> FinalForecast:
    base = _forecast().model_dump()
    return FinalForecast(
        **base,
        final_bias=FinalBias.bullish,
        actionability=Actionability.trade_candidate,
        prompt_versions=[
            PromptVersionMetadata(
                prompt_key="trading_committee.chair.system",
                version="1.0.0",
                prompt_type="system",
                agent_name="chair",
                node_name="agent_trading_committee_chair",
                model_family="gpt-4.1",
                is_active=True,
                rendered_variable_names=["evidence_package"],
                output_schema_ref="CommitteeDecision",
            )
        ],
        validation_status=None,
        committee_decision=None,
        evidence_package=None,
        bull_opening_case=None,
        bear_opening_case=None,
        bull_rebuttal=None,
        bear_rebuttal=None,
        bull_final_position=None,
        bear_final_position=None,
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


def _seed_market_data(repository: InMemoryForecastRepository) -> None:
    bars = [
        DailyBar(
            date=datetime(2024, 1, 1).date(),
            open=2040,
            high=2050,
            low=2030,
            close=2045,
            source="unit",
            symbol="XAUUSD",
        ),
        DailyBar(
            date=datetime(2024, 1, 2).date(),
            open=2045,
            high=2060,
            low=2040,
            close=2055,
            source="unit",
            symbol="XAUUSD",
        ),
        DailyBar(
            date=datetime(2024, 1, 3).date(),
            open=2050,
            high=2065,
            low=2045,
            close=2058,
            source="unit",
            symbol="XAUUSD",
        ),
        DailyBar(
            date=datetime(2024, 1, 4).date(),
            open=2052,
            high=2070,
            low=2048,
            close=2061,
            source="unit",
            symbol="XAUUSD",
        ),
        DailyBar(
            date=datetime(2024, 1, 5).date(),
            open=2055,
            high=2072,
            low=2050,
            close=2064,
            source="unit",
            symbol="XAUUSD",
        ),
        DailyBar(
            date=datetime(2024, 1, 8).date(),
            open=2058,
            high=2075,
            low=2052,
            close=2068,
            source="unit",
            symbol="XAUUSD",
        ),
    ]
    import asyncio

    asyncio.run(repository.upsert_market_bars(bars))
