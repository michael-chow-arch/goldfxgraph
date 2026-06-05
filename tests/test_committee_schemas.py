from __future__ import annotations

from datetime import UTC, datetime

from goldfxgraph.schemas.forecast import (
    Actionability,
    CommitteeDecision,
    DebateCase,
    DebateRebuttal,
    DebateSide,
    DebateStance,
    DecisionValidationResult,
    EvidencePackage,
    EvidencePackageItem,
    FinalBias,
    FinalDebatePosition,
    FinalForecast,
    ForecastDirection,
    ForecastResult,
    LongPlan,
    PromptVersionMetadata,
    RangePlan,
    ShortPlan,
    ValidationResult,
)


def _reference_time() -> datetime:
    return datetime(2024, 1, 2, 8, 30, tzinfo=UTC)


def _evidence_package() -> EvidencePackage:
    reference_time = _reference_time()
    return EvidencePackage(
        symbol="XAUUSD",
        reference_time=reference_time,
        data_timestamp=reference_time,
        data_source="TradingView",
        summary="委员会证据包汇总了各 specialist 的结构化信号。",
        items=[
            EvidencePackageItem(
                item_id="technical-1",
                specialist_name="technical",
                category="technical",
                signal="bullish continuation",
                confidence=0.72,
                key_evidence=["price above sma20", "rsi rising"],
                risk_factors=["near resistance"],
                invalidation_conditions=["close below 2038"],
                important_levels=["2040 support", "2065 resistance"],
                data_freshness="fresh",
                tool_status="ok",
                evidence_refs=["bars:latest", "indicator:rsi_14"],
            )
        ],
        notes=["只允许引用 evidence package 中的事实。"],
    )


def _debate_case() -> DebateCase:
    return DebateCase(
        side="bull",
        thesis="价格仍偏强，适合回踩后观察多头延续。",
        evidence_item_refs=["technical-1"],
        entry_zone="2048-2052",
        stop_loss_or_invalidation="2038",
        target_zone="2075-2088",
        risk_reward=2.1,
        weakness_acknowledged=["上方仍有短线阻力"],
        supporting_arguments=["趋势未破坏", "动能仍在延续"],
    )


def _rebuttal() -> DebateRebuttal:
    return DebateRebuttal(
        side="bull",
        responds_to_side="bear",
        rebutted_points=["空方把短阻力误判为结构反转"],
        accepted_points=["波动率有所上升"],
        plan_adjustments=["将入场从追价改为回踩确认"],
        confidence_trend="down",
        confidence_change=-0.08,
        evidence_item_refs=["technical-1"],
    )


def _final_position() -> FinalDebatePosition:
    return FinalDebatePosition(
        side="bull",
        stance="maintain",
        confidence=0.66,
        confidence_change=-0.04,
        adopted_arguments=["趋势未破坏"],
        rejected_arguments=["短线阻力已足以推翻结构"],
        plan_adjustments=["只在回踩确认后考虑执行"],
        abandon_conditions=["收盘跌破 2038"],
        evidence_item_refs=["technical-1"],
    )


def _committee_decision() -> CommitteeDecision:
    evidence_package = _evidence_package()
    bull_case = _debate_case()
    bear_case = bull_case.model_copy(
        update={"side": DebateSide.bear, "thesis": "价格受阻，需等待更明确的突破确认。"}
    )
    bull_rebuttal = _rebuttal()
    bear_rebuttal = bull_rebuttal.model_copy(
        update={"side": DebateSide.bear, "responds_to_side": DebateSide.bull}
    )
    bull_position = _final_position()
    bear_position = bull_position.model_copy(
        update={
            "side": DebateSide.bear,
            "stance": DebateStance.soften,
            "confidence": 0.58,
            "confidence_change": -0.12,
        }
    )

    return CommitteeDecision(
        evidence_package=evidence_package,
        bull_opening_case=bull_case,
        bear_opening_case=bear_case,
        bull_rebuttal=bull_rebuttal,
        bear_rebuttal=bear_rebuttal,
        bull_final_position=bull_position,
        bear_final_position=bear_position,
        final_bias=FinalBias.bullish,
        actionability=Actionability.trade_candidate,
        winning_side="bull",
        adopted_arguments=["趋势未破坏"],
        rejected_arguments=["短线阻力足以否定多头结构"],
        long_plan=LongPlan(
            entry_zone="2048-2052",
            stop_loss="2038",
            invalidation_level="2035",
            target_zone="2075-2088",
            risk_reward=2.1,
            conditions_to_enter=["回踩后重新站上 2050"],
            conditions_to_abort=["收盘跌破 2038"],
            evidence_item_refs=["technical-1"],
        ),
        short_plan=ShortPlan(
            entry_zone="2048-2044",
            stop_loss="2060",
            invalidation_level="2065",
            target_zone="2032-2024",
            risk_reward=1.8,
            conditions_to_enter=["反弹失败且重新跌回 2045 下方"],
            conditions_to_abort=["价格重新站上 2060"],
            evidence_item_refs=["technical-1"],
        ),
        range_plan=RangePlan(
            upper_sell_zone="2075-2088",
            lower_buy_zone="2038-2045",
            upper_stop="2092",
            lower_stop="2028",
            midline_target="2050",
            breakout_confirmation_level="2092",
            breakdown_confirmation_level="2028",
            range_invalidated_if="日线收盘突破 2092 或跌破 2028",
            risk_reward=1.4,
            conditions_to_enter=["价格维持在震荡区间内"],
            conditions_to_abort=["突破确认失效"],
        ),
        wait_conditions=["若失守 2038，则暂停多头计划"],
        confidence_score=0.66,
        decision_summary="多头赢得委员会，但只能在回踩确认后执行。",
        risk_notes=["上方阻力仍然存在", "需要严格执行失效条件"],
    )


def _validation_result() -> DecisionValidationResult:
    reference_time = _reference_time()
    return DecisionValidationResult(
        is_valid=True,
        checked_at=reference_time,
        summary="委员会输出通过规则校验。",
        errors=[],
        warnings=[],
        validation_rules=["final_bias_present", "actionability_present", "confidence_in_range"],
    )


def _prompt_version() -> PromptVersionMetadata:
    return PromptVersionMetadata(
        prompt_key="committee.chair",
        version="2025-05-01",
        prompt_type="chair_decision",
        agent_name="trading_committee_chair",
        node_name="agent_trading_committee_chair",
        model_family="gpt-4.1",
        is_active=True,
        rendered_variable_names=["evidence_package", "opening_cases", "rebuttals", "final_positions"],
        output_schema_ref="CommitteeDecision",
    )


def _final_forecast() -> FinalForecast:
    reference_time = _reference_time()
    return FinalForecast(
        id=101,
        run_id=88,
        reference_time=reference_time,
        data_timestamp=reference_time,
        data_source="TradingView",
        current_price=2051.75,
        daily_open=2040.0,
        daily_high=2063.5,
        daily_low=2035.25,
        daily_close=2055.1,
        direction=ForecastDirection.bullish,
        window_directions=[],
        entry_price=2051.0,
        entry_price_low=2048.5,
        entry_price_high=2053.5,
        take_profit_price=2078.0,
        stop_loss_price=2038.0,
        holding_period="1-3 days",
        intraday_action="回踩确认后分批观察",
        long_term_action="中线继续观察趋势延续",
        confidence_score=0.64,
        technical_summary="技术面偏多",
        macro_summary="宏观面中性偏多",
        news_summary="新闻面影响有限",
        market_sentiment_summary="市场情绪温和偏多",
        alt_data_summary="另类数据暂未出现明显背离",
        risk_summary="波动风险可控",
        agent_votes=[],
        risk_notes=["仅供研究", "请结合仓位管理"],
        final_bias=FinalBias.bullish,
        actionability=Actionability.trade_candidate,
        evidence_package=_evidence_package(),
        committee_decision=_committee_decision(),
        validation_status=_validation_result(),
        prompt_versions=[_prompt_version()],
    )


def test_committee_enums_cover_required_values() -> None:
    assert {bias.value for bias in FinalBias} == {"bullish", "bearish", "range_bound", "cautious"}
    assert {item.value for item in Actionability} == {
        "trade_candidate",
        "prepare_only",
        "observe_only",
        "no_trade",
    }


def test_committee_schema_models_validate_and_serialize() -> None:
    evidence_package = _evidence_package()
    debate_case = _debate_case()
    rebuttal = _rebuttal()
    final_position = _final_position()
    committee_decision = _committee_decision()
    validation_result = _validation_result()
    prompt_version = _prompt_version()

    serialized = committee_decision.model_dump(mode="json")

    assert evidence_package.items[0].tool_status == "ok"
    assert debate_case.side == "bull"
    assert rebuttal.confidence_trend == "down"
    assert final_position.stance == "maintain"
    assert committee_decision.final_bias == FinalBias.bullish
    assert serialized["final_bias"] == "bullish"
    assert serialized["actionability"] == "trade_candidate"
    assert serialized["long_plan"]["entry_zone"] == "2048-2052"
    assert serialized["short_plan"]["entry_zone"] == "2048-2044"
    assert serialized["range_plan"]["breakout_confirmation_level"] == "2092"
    assert validation_result.is_valid is True
    assert prompt_version.rendered_variable_names == [
        "evidence_package",
        "opening_cases",
        "rebuttals",
        "final_positions",
    ]
    assert ValidationResult is DecisionValidationResult


def test_final_forecast_adds_committee_payload_without_changing_legacy_contract() -> None:
    final_forecast = _final_forecast()
    payload = final_forecast.model_dump(mode="json")

    assert payload["direction"] == "bullish"
    assert payload["final_bias"] == "bullish"
    assert payload["actionability"] == "trade_candidate"
    assert payload["committee_decision"]["winning_side"] == "bull"
    assert payload["validation_status"]["is_valid"] is True
    assert payload["prompt_versions"][0]["prompt_key"] == "committee.chair"
    assert payload["evidence_package"]["items"][0]["specialist_name"] == "technical"
    assert "final_bias" not in ForecastResult.model_fields
    assert "committee_decision" not in ForecastResult.model_fields
    assert "validation_status" not in ForecastResult.model_fields
    assert "prompt_versions" not in ForecastResult.model_fields
