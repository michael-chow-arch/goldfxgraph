from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from goldfxgraph.market_data.current_quote import QuoteProviderError
from goldfxgraph.research import cli as research_cli
from goldfxgraph.schemas.forecast import AgentVote, ForecastDirection, ForecastResult, ResearchRunResult


class _FakeEngine:
    async def dispose(self) -> None:  # pragma: no cover - trivial helper
        return None


class _FakeSessionFactory:
    def __init__(self) -> None:
        self.engine = _FakeEngine()


class _FakeRepository:
    def __init__(self) -> None:
        self.runs: dict[int, ResearchRunResult] = {}
        self.next_run_id = 1

    async def create_research_run(self, input_summary: dict[str, object]):
        run_id = self.next_run_id
        self.next_run_id += 1
        self.runs[run_id] = ResearchRunResult(
            id=run_id,
            status="running",
            started_at=datetime.now(UTC),
            input_summary=dict(input_summary),
        )
        return type("Run", (), {"id": run_id})()

    async def mark_run_failed(self, run_id: int, error_message: str) -> None:
        run = self.runs[run_id]
        self.runs[run_id] = run.model_copy(
            update={"status": "failed", "completed_at": datetime.now(UTC), "error_message": error_message}
        )

    async def get_research_run(self, run_id: int) -> ResearchRunResult | None:
        return self.runs.get(run_id)


def test_research_cli_reruns_workflow(monkeypatch) -> None:
    fake_repo = _FakeRepository()
    fake_forecast = ForecastResult(
        id=1,
        run_id=1,
        data_timestamp=datetime.now(UTC),
        data_source="unit-test",
        current_price=2060.0,
        daily_open=2050.0,
        daily_high=2065.0,
        daily_low=2042.0,
        daily_close=2058.0,
        direction=ForecastDirection.neutral,
        entry_price=2060.0,
        take_profit_price=2070.0,
        stop_loss_price=2050.0,
        holding_period="1-3 个交易日，等待方向确认",
        intraday_action="研究情景中性：关注 2060.00 附近区间反应，等待突破或跌破后再更新假设。",
        long_term_action="中期研究维持观望，等待趋势指标和外部数据给出更清晰方向。",
        confidence_score=0.55,
        technical_summary="技术面测试",
        macro_summary="宏观面测试",
        news_summary="新闻测试",
        market_sentiment_summary="情绪测试",
        alt_data_summary="另类数据测试",
        risk_summary="风险测试",
        agent_votes=[
            AgentVote(agent="technical", direction=ForecastDirection.neutral, confidence=0.55, rationale="ok"),
        ],
        risk_notes=[],
    )

    async def fake_run_forecast_workflow(**kwargs):
        fake_repo.runs[1] = fake_repo.runs[1].model_copy(update={"forecast": fake_forecast})
        return {}

    monkeypatch.setattr(research_cli, "create_session_factory", lambda database_url: _FakeSessionFactory())
    monkeypatch.setattr(research_cli, "init_models", lambda engine: asyncio.sleep(0))
    monkeypatch.setattr(research_cli, "validate_required_prompt_templates", lambda session_factory: asyncio.sleep(0))
    monkeypatch.setattr(research_cli, "validate_required_external_sources", lambda session_factory: asyncio.sleep(0))
    monkeypatch.setattr(research_cli, "ForecastRepository", lambda session_factory: fake_repo)
    monkeypatch.setattr(research_cli, "run_forecast_workflow", fake_run_forecast_workflow)

    exit_code = asyncio.run(
        research_cli._run_research(
            settings=type("Settings", (), {"database_url": "sqlite+aiosqlite:///:memory:"})(),
            entrypoint="cli",
        )
    )

    assert exit_code == 0
    assert fake_repo.runs[1].forecast is fake_forecast


def test_research_cli_fails_when_freshness_preflight_fails(monkeypatch) -> None:
    fake_repo = _FakeRepository()

    async def fake_run_eod_backfill(**kwargs):
        return type(
            "Result",
            (),
            {
                "status": "failed",
                "failure_reason": "TradingView history unavailable",
                "written": False,
            },
        )()

    monkeypatch.setattr(research_cli, "create_session_factory", lambda database_url: _FakeSessionFactory())
    monkeypatch.setattr(research_cli, "init_models", lambda engine: asyncio.sleep(0))
    monkeypatch.setattr(research_cli, "validate_required_prompt_templates", lambda session_factory: asyncio.sleep(0))
    monkeypatch.setattr(research_cli, "validate_required_external_sources", lambda session_factory: asyncio.sleep(0))
    monkeypatch.setattr(research_cli, "ForecastRepository", lambda session_factory: fake_repo)
    monkeypatch.setattr("goldfxgraph.workflow.nodes.run_eod_backfill", fake_run_eod_backfill)

    exit_code = asyncio.run(
        research_cli._run_research(
            settings=type("Settings", (), {"database_url": "sqlite+aiosqlite:///:memory:"})(),
            entrypoint="cli",
        )
    )

    assert exit_code == 1
    assert fake_repo.runs[1].status == "failed"
    assert "market data freshness" in fake_repo.runs[1].error_message


def test_research_cli_marks_run_failed_when_workflow_fails(monkeypatch) -> None:
    fake_repo = _FakeRepository()

    async def fake_run_forecast_workflow(**kwargs):
        raise QuoteProviderError("market data freshness check failed: TradingView history unavailable")

    monkeypatch.setattr(research_cli, "create_session_factory", lambda database_url: _FakeSessionFactory())
    monkeypatch.setattr(research_cli, "init_models", lambda engine: asyncio.sleep(0))
    monkeypatch.setattr(research_cli, "validate_required_prompt_templates", lambda session_factory: asyncio.sleep(0))
    monkeypatch.setattr(research_cli, "validate_required_external_sources", lambda session_factory: asyncio.sleep(0))
    monkeypatch.setattr(research_cli, "ForecastRepository", lambda session_factory: fake_repo)
    monkeypatch.setattr(research_cli, "run_forecast_workflow", fake_run_forecast_workflow)

    exit_code = asyncio.run(
        research_cli._run_research(
            settings=type("Settings", (), {"database_url": "sqlite+aiosqlite:///:memory:"})(),
            entrypoint="cli",
        )
    )

    assert exit_code == 1
    assert fake_repo.runs[1].status == "failed"
    assert "market data freshness" in fake_repo.runs[1].error_message
