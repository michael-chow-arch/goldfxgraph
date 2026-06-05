from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, inspect, select

from goldfxgraph.persistence import (
    create_session_factory,
    init_models,
    REQUIRED_PROMPT_KEYS,
)
from goldfxgraph.persistence.models import PromptTemplateModel
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.persistence.seed_external_sources import (
    REQUIRED_EXTERNAL_SOURCE_KEYS,
    validate_required_external_sources,
)
from goldfxgraph.persistence.seed_prompt_templates import validate_required_prompt_templates
from goldfxgraph.schemas.forecast import (
    Actionability,
    AgentVote,
    CommitteeDecision,
    DebateCase,
    DebateRebuttal,
    DebateSide,
    DebateStance,
    DecisionValidationResult,
    EvidencePackage,
    EvidencePackageItem,
    EvidenceToolStatus,
    FinalBias,
    FinalDebatePosition,
    FinalForecast,
    ForecastDirection,
    ForecastResult,
    ForecastWindowDirection,
    LongPlan,
    PromptVersionMetadata,
)

from conftest import seed_runtime_registry

pytestmark = pytest.mark.asyncio


def _forecast(
    *,
    reference_time: datetime | None = None,
    direction: ForecastDirection = ForecastDirection.bullish,
) -> ForecastResult:
    now = reference_time or datetime.now(UTC)
    return ForecastResult(
        reference_time=now,
        data_timestamp=now,
        data_source="unit",
        current_price=2050,
        daily_open=2040,
        daily_high=2060,
        daily_low=2035,
        daily_close=2048,
        direction=direction,
        window_directions=[
            ForecastWindowDirection(
                window_label="0-3天",
                direction=direction,
                strength="moderate",
                confidence=0.63,
                reason="短线趋势延续",
            )
        ],
        entry_price=2049,
        entry_price_low=2047,
        entry_price_high=2051,
        take_profit_price=2075,
        stop_loss_price=2032,
        holding_period="1-3 days",
        intraday_action="等待回踩确认",
        long_term_action="仅适合小仓位研究观察",
        confidence_score=0.62,
        technical_summary="技术面偏强",
        macro_summary="宏观面中性",
        news_summary="新闻面中性",
        risk_summary="波动风险较高",
        agent_votes=[
            AgentVote(
                agent="technical",
                direction=direction,
                confidence=0.7,
                rationale="trend",
            )
        ],
        risk_notes=["仅供研究"],
    )


def _committee_forecast() -> FinalForecast:
    now = datetime.now(UTC)
    evidence_package = EvidencePackage(
        symbol="XAUUSD",
        reference_time=now,
        data_timestamp=now,
        data_source="TradingView",
        summary="证据包摘要",
        items=[
            EvidencePackageItem(
                item_id="technical",
                specialist_name="technical",
                category="price_action",
                signal="bullish",
                confidence=0.71,
                key_evidence=["技术面偏多"],
                risk_factors=["波动仍在"],
                invalidation_conditions=["跌破 2038"],
                important_levels=["2050-2060"],
                data_freshness="fresh",
                tool_status=EvidenceToolStatus.ok,
                evidence_refs=["technical_summary"],
            )
        ],
        notes=["仅供研究"],
    )
    bull_opening_case = DebateCase(
        side=DebateSide.bull,
        thesis="看多开场",
        evidence_item_refs=["technical"],
        entry_zone="2050-2055",
        stop_loss_or_invalidation="2038",
        target_zone="2075-2080",
        risk_reward=2.1,
        weakness_acknowledged=["回撤风险"],
        supporting_arguments=["技术偏多"],
        confidence=0.68,
    )
    bear_opening_case = DebateCase(
        side=DebateSide.bear,
        thesis="看空开场",
        evidence_item_refs=["technical"],
        entry_zone="2055-2060",
        stop_loss_or_invalidation="2068",
        target_zone="2035-2040",
        risk_reward=2.0,
        weakness_acknowledged=["趋势仍有延续可能"],
        supporting_arguments=["阻力仍然存在"],
        confidence=0.57,
    )
    bull_rebuttal = DebateRebuttal(
        side=DebateSide.bull,
        responds_to_side=DebateSide.bear,
        rebutted_points=["阻力仍在"],
        accepted_points=["波动风险仍存在"],
        plan_adjustments=["等待回踩确认"],
        confidence_trend="up",
        confidence_change=0.02,
        evidence_item_refs=["technical"],
    )
    bear_rebuttal = DebateRebuttal(
        side=DebateSide.bear,
        responds_to_side=DebateSide.bull,
        rebutted_points=["趋势延续"],
        accepted_points=["失效条件清晰"],
        plan_adjustments=["收紧止损"],
        confidence_trend="flat",
        confidence_change=0.0,
        evidence_item_refs=["technical"],
    )
    bull_final_position = FinalDebatePosition(
        side=DebateSide.bull,
        stance=DebateStance.maintain,
        confidence=0.7,
        confidence_change=0.02,
        adopted_arguments=["趋势尚未破坏"],
        rejected_arguments=["追涨风险"],
        plan_adjustments=["分批观察"],
        abandon_conditions=["跌破 2038"],
        evidence_item_refs=["technical"],
    )
    bear_final_position = FinalDebatePosition(
        side=DebateSide.bear,
        stance=DebateStance.soften,
        confidence=0.55,
        confidence_change=-0.01,
        adopted_arguments=["上方压力存在"],
        rejected_arguments=["追空性价比不高"],
        plan_adjustments=["观察为主"],
        abandon_conditions=["突破 2068"],
        evidence_item_refs=["technical"],
    )
    committee_decision = CommitteeDecision(
        evidence_package=evidence_package,
        bull_opening_case=bull_opening_case,
        bear_opening_case=bear_opening_case,
        bull_rebuttal=bull_rebuttal,
        bear_rebuttal=bear_rebuttal,
        bull_final_position=bull_final_position,
        bear_final_position=bear_final_position,
        final_bias=FinalBias.bullish,
        actionability=Actionability.trade_candidate,
        winning_side=DebateSide.bull,
        adopted_arguments=["趋势延续", "风险可控"],
        rejected_arguments=["盲目追涨"],
        long_plan=LongPlan(
            entry_zone="2050-2055",
            stop_loss="2038",
            invalidation_level="2036",
            target_zone="2075-2080",
            risk_reward=2.2,
            conditions_to_enter=["回踩确认"],
            conditions_to_abort=["跌破 2038"],
            evidence_item_refs=["technical"],
        ),
        short_plan=None,
        range_plan=None,
        wait_conditions=[],
        confidence_score=0.69,
        decision_summary="委员会看多",
        risk_notes=["仅供研究"],
        evidence_item_refs=["technical"],
    )
    return FinalForecast(
        **_forecast().model_dump(),
        final_bias=FinalBias.bullish,
        actionability=Actionability.trade_candidate,
        evidence_package=evidence_package,
        committee_decision=committee_decision,
        validation_status=DecisionValidationResult(
            is_valid=True,
            checked_at=now,
            summary="通过",
            errors=[],
            warnings=[],
            validation_rules=["confidence_in_range"],
        ),
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
    )


async def test_repository_saves_run_and_latest_forecast() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    run = await repo.create_research_run(input_summary={"symbol": "XAUUSD"})
    saved = await repo.save_forecast(run.id, _forecast())
    await repo.mark_run_success(run.id)
    latest = await repo.get_latest_forecast()
    loaded_run = await repo.get_research_run(run.id)

    assert saved.id is not None
    assert latest is not None
    assert latest.direction == ForecastDirection.bullish
    assert latest.reference_time.tzinfo is not None
    assert latest.data_timestamp.tzinfo is not None
    assert loaded_run is not None
    assert loaded_run.status == "success"
    assert loaded_run.started_at.tzinfo is not None
    assert loaded_run.forecast is not None
    assert loaded_run.forecast.window_directions[0].window_label == "0-3天"
    assert loaded_run.forecast.entry_price_low == 2047
    assert loaded_run.forecast.entry_price_high == 2051


async def test_repository_round_trips_committee_forecast_metadata() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    run = await repo.create_research_run(input_summary={"symbol": "XAUUSD", "flow": "committee"})
    saved = await repo.save_forecast(run.id, _committee_forecast())
    loaded = await repo.get_latest_forecast()
    loaded_run = await repo.get_research_run(run.id)

    assert saved.id is not None
    assert loaded is not None
    assert isinstance(loaded, FinalForecast)
    assert loaded.final_bias == FinalBias.bullish
    assert loaded.actionability == Actionability.trade_candidate
    assert loaded.evidence_package is not None
    assert loaded.committee_decision is not None
    assert loaded.validation_status is not None
    assert loaded.prompt_versions[0].prompt_key == "trading_committee.chair.system"
    assert loaded_run is not None
    assert loaded_run.forecast is not None
    assert isinstance(loaded_run.forecast, FinalForecast)
    assert loaded_run.forecast.committee_decision is not None
    assert loaded_run.forecast.prompt_versions[0].version == "1.0.0"
    assert loaded_run.forecast.committee_decision.long_plan is not None


async def test_repository_persists_scheduler_run_status_snapshot() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    run = await repo.create_scheduler_run(input_summary={"symbol": "XAUUSD"})
    updated = await repo.update_scheduler_run_stage(
        run.id,
        current_stage="agent_technical_analysis",
        agent_statuses=[{"agent": "technical", "status": "running"}],
        agent_diagnostics=[
            {
                "agent": "technical",
                "stage": "agent_technical_analysis",
                "status": "failed",
                "message": "OpenAI-compatible technical agent 调用失败，已标记为失败，不生成兜底输出。",
                "detail": "HTTP 500",
            }
        ],
    )
    latest = await repo.get_latest_scheduler_run()

    assert run.id is not None
    assert updated.id == run.id
    assert updated.current_stage == "agent_technical_analysis"
    assert updated.agent_statuses == [{"agent": "technical", "status": "running"}]
    assert updated.agent_diagnostics[0]["detail"] == "HTTP 500"
    assert latest is not None
    assert latest.id == run.id
    assert latest.current_stage == "agent_technical_analysis"
    assert latest.agent_statuses[0]["status"] == "running"
    assert latest.agent_diagnostics[0]["agent"] == "technical"


async def test_repository_records_failed_run() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    run = await repo.create_research_run(input_summary={"symbol": "XAUUSD"})
    await repo.mark_run_failed(run.id, "CSV 缺少 low 字段")
    loaded = await repo.get_research_run(run.id)

    assert loaded is not None
    assert loaded.status == "failed"
    assert loaded.error_message == "CSV 缺少 low 字段"


async def test_repository_returns_newest_forecast_and_round_trips_json_fields() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)
    older_time = datetime.now(UTC) - timedelta(hours=1)
    newer_time = datetime.now(UTC)

    older_run = await repo.create_research_run(input_summary={"symbol": "XAUUSD", "window": "older"})
    await repo.save_forecast(older_run.id, _forecast(reference_time=older_time, direction=ForecastDirection.neutral))
    newer_run = await repo.create_research_run(input_summary={"symbol": "XAUUSD", "window": "newer"})
    newer = await repo.save_forecast(
        newer_run.id,
        _forecast(reference_time=newer_time, direction=ForecastDirection.bullish),
    )

    latest = await repo.get_latest_forecast()
    loaded_run = await repo.get_research_run(newer_run.id)

    assert latest is not None
    assert latest.id == newer.id
    assert latest.agent_votes == newer.agent_votes
    assert latest.risk_notes == ["仅供研究"]
    assert loaded_run is not None
    assert loaded_run.input_summary["window"] == "newer"


async def test_repository_serializes_json_safe_input_summary() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)
    observed_at = datetime(2024, 1, 1, 8, 30, tzinfo=UTC)

    run = await repo.create_research_run(input_summary={"symbol": "XAUUSD", "observed_at": observed_at})
    loaded_run = await repo.get_research_run(run.id)

    assert loaded_run is not None
    assert loaded_run.input_summary["observed_at"] == "2024-01-01T08:30:00Z"


async def test_repository_returns_none_for_missing_research_run() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    assert await repo.get_research_run(999) is None


async def test_init_models_backfills_missing_forecast_columns() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    async with session_factory.engine.begin() as connection:
        await connection.exec_driver_sql(
            """
            CREATE TABLE forecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL UNIQUE,
                created_at DATETIME NOT NULL,
                symbol VARCHAR(32) NOT NULL,
                reference_time DATETIME NOT NULL,
                data_timestamp DATETIME NOT NULL,
                data_source VARCHAR(255) NOT NULL,
                current_price FLOAT NOT NULL,
                daily_open FLOAT NOT NULL,
                daily_high FLOAT NOT NULL,
                daily_low FLOAT NOT NULL,
                daily_close FLOAT NOT NULL,
                direction VARCHAR(16) NOT NULL,
                window_directions JSON NOT NULL,
                entry_price FLOAT,
                entry_price_low FLOAT,
                entry_price_high FLOAT,
                take_profit_price FLOAT,
                stop_loss_price FLOAT,
                holding_period VARCHAR(255) NOT NULL,
                intraday_action TEXT NOT NULL,
                long_term_action TEXT NOT NULL,
                confidence_score FLOAT NOT NULL,
                technical_summary TEXT NOT NULL,
                macro_summary TEXT,
                news_summary TEXT,
                risk_summary TEXT NOT NULL,
                agent_votes JSON NOT NULL,
                risk_notes JSON NOT NULL,
                disclaimer TEXT NOT NULL
            )
            """
        )

    await init_models(session_factory.engine)

    async with session_factory.engine.begin() as connection:
        columns = await connection.run_sync(
            lambda sync_connection: {column["name"] for column in inspect(sync_connection).get_columns("forecasts")}
        )

    assert "market_sentiment_summary" in columns
    assert "alt_data_summary" in columns
    assert "window_directions" in columns
    assert "entry_price_low" in columns
    assert "entry_price_high" in columns
    assert "evidence_package" in columns
    assert "committee_decision" in columns
    assert "validation_status" in columns
    assert "prompt_versions" in columns


async def test_init_models_creates_prompt_template_table() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)

    async with session_factory.engine.begin() as connection:
        table_names = await connection.run_sync(lambda sync_connection: inspect(sync_connection).get_table_names())
        prompt_columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"] for column in inspect(sync_connection).get_columns("prompt_templates")
            }
        )

    assert "prompt_templates" in table_names
    assert "prompt_key" in prompt_columns
    assert "version" in prompt_columns
    assert "prompt_text_en" in prompt_columns
    assert "prompt_text_zh" in prompt_columns
    assert "variables_schema" in prompt_columns
    assert "is_active" in prompt_columns


async def test_required_prompt_and_external_source_validation_succeeds_when_seeded() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)

    await seed_runtime_registry(session_factory)

    prompt_count = await validate_required_prompt_templates(session_factory)
    source_count = await validate_required_external_sources(session_factory)

    async with session_factory.sessionmaker() as session:
        total_rows = await session.scalar(select(func.count(PromptTemplateModel.id)))
        active_counts_result = await session.execute(
            select(
                PromptTemplateModel.prompt_key,
                func.count(PromptTemplateModel.id),
            )
            .where(PromptTemplateModel.is_active.is_(True))
            .group_by(PromptTemplateModel.prompt_key)
        )
        prompt_rows_result = await session.execute(
            select(
                PromptTemplateModel.prompt_key,
                PromptTemplateModel.version,
                PromptTemplateModel.prompt_type,
                PromptTemplateModel.is_active,
            ).order_by(PromptTemplateModel.prompt_key.asc(), PromptTemplateModel.prompt_type.asc())
        )

    active_counts = dict(active_counts_result.all())
    prompt_rows = prompt_rows_result.all()

    assert prompt_count == len(REQUIRED_PROMPT_KEYS)
    assert source_count == len(REQUIRED_EXTERNAL_SOURCE_KEYS)
    assert total_rows == len(REQUIRED_PROMPT_KEYS)
    assert set(active_counts.values()) == {1}
    assert {row[0] for row in prompt_rows} == set(REQUIRED_PROMPT_KEYS)
    assert {row[2] for row in prompt_rows} == {"system", "user"}
    assert all(row[3] is True for row in prompt_rows)
