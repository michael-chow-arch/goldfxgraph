from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TypedDict

import httpx
from pydantic import BaseModel, Field

from goldfxgraph.indicators.technical import compute_technical_indicators
from goldfxgraph.llm.openai_client import OpenAIAgentClient, OpenAIClientError
from goldfxgraph.market_data.csv_loader import load_xauusd_daily_csv
from goldfxgraph.market_data.current_quote import CurrentQuoteProvider
from goldfxgraph.packages.common.settings import GoldFXGraphSettings, get_settings
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import (
    AgentVote,
    CurrentQuote,
    DailyBar,
    ForecastDirection,
    ForecastResult,
    MarketDataSet,
    TechnicalIndicators,
)


class QuoteProvider(Protocol):
    def fetch(self) -> CurrentQuote: ...


class WorkflowState(TypedDict, total=False):
    settings: GoldFXGraphSettings
    csv_path: Path | str
    quote_provider: QuoteProvider
    agent_http_transport: httpx.BaseTransport
    repository: ForecastRepository
    market_data: MarketDataSet
    bars: list[DailyBar]
    latest_bar: DailyBar
    quote: CurrentQuote
    indicators: TechnicalIndicators
    technical_summary: str
    macro_summary: str
    news_summary: str
    risk_summary: str
    agent_votes: list[AgentVote]
    risk_notes: list[str]
    forecast: ForecastResult
    run_id: int
    persistence_status: str
    errors: list[str]
    result: ForecastResult


RESEARCH_DISCLAIMER = "本结果仅用于研究和决策支持，不构成金融建议、投资建议或交易指令。"


class AgentApiResponse(BaseModel):
    summary: str
    direction: ForecastDirection
    confidence: float = Field(ge=0, le=1)
    risk_notes: list[str] = Field(default_factory=list)


def create_research_forecast_from_inputs(
    latest_bar: DailyBar,
    quote: CurrentQuote,
    indicators: TechnicalIndicators,
) -> ForecastResult:
    price = quote.current_price
    atr = _usable_atr(indicators, latest_bar, price)
    direction = _direction_from_inputs(price, latest_bar, indicators)
    entry_price, take_profit_price, stop_loss_price = _research_levels(price, atr, direction)
    technical_summary = _technical_summary(price, latest_bar, indicators, direction)
    macro_summary = "宏观信息未接入外部实时数据源，本轮仅记录为中性背景，等待后续 API 层补充可验证来源。"
    news_summary = "新闻信息未接入外部实时数据源，本轮不使用未经验证的新闻假设影响方向判断。"
    risk_notes = _risk_notes(latest_bar, indicators, atr)
    risk_summary = "风险评估基于 ATR、日内区间和指标可用性生成，建议仅作为研究参考并控制仓位暴露。"
    agent_votes = [
        AgentVote(
            agent="technical",
            direction=direction,
            confidence=_technical_confidence(indicators, direction),
            rationale=technical_summary,
        ),
        AgentVote(
            agent="macro",
            direction=ForecastDirection.neutral,
            confidence=0.35,
            rationale=macro_summary,
        ),
        AgentVote(
            agent="news",
            direction=ForecastDirection.neutral,
            confidence=0.35,
            rationale=news_summary,
        ),
        AgentVote(
            agent="risk",
            direction=_risk_vote_direction(direction, atr, price),
            confidence=0.55,
            rationale=risk_summary,
        ),
    ]

    return ForecastResult(
        symbol=quote.symbol or latest_bar.symbol,
        reference_time=datetime.now(UTC),
        data_timestamp=quote.data_timestamp,
        data_source=quote.data_source,
        current_price=round(price, 6),
        daily_open=latest_bar.open,
        daily_high=latest_bar.high,
        daily_low=latest_bar.low,
        daily_close=latest_bar.close,
        direction=direction,
        entry_price=entry_price,
        take_profit_price=take_profit_price,
        stop_loss_price=stop_loss_price,
        holding_period=_holding_period(direction, atr, price),
        intraday_action=_intraday_action(direction, entry_price, take_profit_price, stop_loss_price),
        long_term_action=_long_term_action(direction),
        confidence_score=_combined_confidence(agent_votes, indicators),
        technical_summary=technical_summary,
        macro_summary=macro_summary,
        news_summary=news_summary,
        risk_summary=risk_summary,
        agent_votes=agent_votes,
        risk_notes=risk_notes,
        disclaimer=RESEARCH_DISCLAIMER,
    )


def router_validate_request(state: WorkflowState) -> WorkflowState:
    if "errors" in state and state["errors"]:
        raise ValueError("; ".join(state["errors"]))
    return state


def tool_load_market_data(state: WorkflowState) -> WorkflowState:
    if "market_data" in state and "latest_bar" in state and "bars" in state:
        return state

    settings = state.get("settings") or get_settings()
    csv_path = Path(state.get("csv_path") or settings.xauusd_csv_path)
    market_data = load_xauusd_daily_csv(csv_path)
    return {
        **state,
        "settings": settings,
        "market_data": market_data,
        "bars": market_data.bars,
        "latest_bar": market_data.latest_bar,
    }


def tool_fetch_current_gold_quote(state: WorkflowState) -> WorkflowState:
    if "quote" in state:
        return state

    provider = state.get("quote_provider")
    if provider is None:
        settings = state.get("settings") or get_settings()
        provider_kwargs: dict[str, str] = {}
        if settings.current_quote_url:
            provider_kwargs["url"] = settings.current_quote_url
        if settings.current_quote_api_key:
            provider_kwargs["api_key"] = settings.current_quote_api_key.get_secret_value()
        provider = CurrentQuoteProvider(**provider_kwargs)

    quote = provider.fetch()
    return {**state, "quote": quote}


def tool_compute_indicators(state: WorkflowState) -> WorkflowState:
    if "indicators" in state:
        return state

    bars = state.get("bars")
    if bars is None:
        market_data = state.get("market_data")
        bars = market_data.bars if market_data else None
    if not bars:
        raise ValueError("workflow state missing daily bars for technical indicator calculation")

    return {**state, "indicators": compute_technical_indicators(bars)}


def agent_technical_analysis(state: WorkflowState) -> WorkflowState:
    latest_bar = _required(state, "latest_bar")
    quote = _required(state, "quote")
    indicators = _required(state, "indicators")
    remote, diagnostic = _remote_agent_response(state, "technical")
    direction = remote.direction if remote else _direction_from_inputs(quote.current_price, latest_bar, indicators)
    vote = AgentVote(
        agent="technical",
        direction=direction,
        confidence=remote.confidence if remote else _technical_confidence(indicators, direction),
        rationale=remote.summary
        if remote
        else _technical_summary(quote.current_price, latest_bar, indicators, direction),
    )
    return {
        **state,
        "technical_summary": vote.rationale,
        "risk_notes": _append_note(state.get("risk_notes"), diagnostic),
        "agent_votes": [*_existing_votes_without(state, "technical"), vote],
    }


def agent_macro_analysis(state: WorkflowState) -> WorkflowState:
    remote, diagnostic = _remote_agent_response(state, "macro")
    summary = (
        remote.summary
        if remote
        else "宏观 agent 暂未调用外部实时宏观源，当前输出保持中性，并要求后续版本记录可验证来源。"
    )
    vote = AgentVote(
        agent="macro",
        direction=remote.direction if remote else ForecastDirection.neutral,
        confidence=remote.confidence if remote else 0.35,
        rationale=summary,
    )
    return {
        **state,
        "macro_summary": summary,
        "risk_notes": _append_note(state.get("risk_notes"), diagnostic),
        "agent_votes": [*_existing_votes_without(state, "macro"), vote],
    }


def agent_news_analysis(state: WorkflowState) -> WorkflowState:
    remote, diagnostic = _remote_agent_response(state, "news")
    summary = remote.summary if remote else "新闻 agent 暂未调用外部实时新闻源，当前不使用未验证新闻作为方向依据。"
    vote = AgentVote(
        agent="news",
        direction=remote.direction if remote else ForecastDirection.neutral,
        confidence=remote.confidence if remote else 0.35,
        rationale=summary,
    )
    return {
        **state,
        "news_summary": summary,
        "risk_notes": _append_note(state.get("risk_notes"), diagnostic),
        "agent_votes": [*_existing_votes_without(state, "news"), vote],
    }


def agent_risk_analysis(state: WorkflowState) -> WorkflowState:
    latest_bar = _required(state, "latest_bar")
    quote = _required(state, "quote")
    indicators = _required(state, "indicators")
    atr = _usable_atr(indicators, latest_bar, quote.current_price)
    remote, diagnostic = _remote_agent_response(state, "risk")
    notes = _merge_notes(
        state.get("risk_notes"),
        remote.risk_notes if remote and remote.risk_notes else _risk_notes(latest_bar, indicators, atr),
    )
    notes = _append_note(notes, diagnostic)
    summary = (
        remote.summary if remote else "风险 agent 基于 ATR、日线区间与指标缺失情况生成结构化提示，不触发任何交易执行。"
    )
    vote = AgentVote(
        agent="risk",
        direction=remote.direction
        if remote
        else _risk_vote_direction(
            _direction_from_inputs(quote.current_price, latest_bar, indicators),
            atr,
            quote.current_price,
        ),
        confidence=remote.confidence if remote else 0.55,
        rationale=summary,
    )
    return {
        **state,
        "risk_summary": summary,
        "risk_notes": notes,
        "agent_votes": [*_existing_votes_without(state, "risk"), vote],
    }


def agent_forecast_planning(state: WorkflowState) -> WorkflowState:
    latest_bar = _required(state, "latest_bar")
    quote = _required(state, "quote")
    indicators = _required(state, "indicators")
    forecast = create_research_forecast_from_inputs(
        latest_bar=latest_bar,
        quote=quote,
        indicators=indicators,
    )

    agent_votes = state.get("agent_votes")
    if agent_votes:
        direction, confidence_score = _aggregate_agent_votes(agent_votes)
        atr = _usable_atr(indicators, latest_bar, quote.current_price)
        entry_price, take_profit_price, stop_loss_price = _research_levels(quote.current_price, atr, direction)
        forecast.direction = direction
        forecast.confidence_score = confidence_score
        forecast.entry_price = entry_price
        forecast.take_profit_price = take_profit_price
        forecast.stop_loss_price = stop_loss_price
        forecast.holding_period = _holding_period(direction, atr, quote.current_price)
        forecast.intraday_action = _intraday_action(direction, entry_price, take_profit_price, stop_loss_price)
        forecast.long_term_action = _long_term_action(direction)
        forecast.agent_votes = agent_votes
    if "technical_summary" in state:
        forecast.technical_summary = state["technical_summary"]
    if "macro_summary" in state:
        forecast.macro_summary = state["macro_summary"]
    if "news_summary" in state:
        forecast.news_summary = state["news_summary"]
    if "risk_summary" in state:
        forecast.risk_summary = state["risk_summary"]
    if "risk_notes" in state:
        forecast.risk_notes = _merge_notes(forecast.risk_notes, state["risk_notes"])

    return {**state, "forecast": forecast}


async def tool_persist_research_run(state: WorkflowState) -> WorkflowState:
    repository = state.get("repository")
    if repository is None:
        return {**state, "persistence_status": "skipped: repository not provided"}
    if "run_id" in state:
        return state

    run = await repository.create_research_run(_input_summary(state))
    return {**state, "run_id": run.id, "persistence_status": "research_run_created"}


async def tool_persist_forecast(state: WorkflowState) -> WorkflowState:
    repository = state.get("repository")
    if repository is None:
        return {**state, "persistence_status": "skipped: repository not provided"}

    forecast = state.get("forecast")
    if forecast is None:
        raise ValueError("workflow state missing forecast for persistence")

    run_id = state.get("run_id")
    if run_id is None:
        state = await tool_persist_research_run(state)
        run_id = state.get("run_id")
    if run_id is None:
        raise ValueError("workflow state missing research run id for forecast persistence")

    saved_forecast = await repository.save_forecast(run_id, forecast)
    await repository.mark_run_success(run_id)
    return {**state, "forecast": saved_forecast, "persistence_status": "forecast_saved"}


def router_finalize_result(state: WorkflowState) -> WorkflowState:
    forecast = state.get("forecast")
    if forecast is None:
        raise ValueError("workflow state missing forecast result")
    return {**state, "result": forecast}


def _direction_from_inputs(
    price: float,
    latest_bar: DailyBar,
    indicators: TechnicalIndicators,
) -> ForecastDirection:
    bullish_score = 0
    bearish_score = 0

    trend_reference = indicators.sma_20 or indicators.ema_12 or latest_bar.close
    if price > trend_reference:
        bullish_score += 1
    elif price < trend_reference:
        bearish_score += 1

    if price > latest_bar.close:
        bullish_score += 1
    elif price < latest_bar.close:
        bearish_score += 1

    if indicators.rsi_14 is not None:
        if indicators.rsi_14 >= 70:
            bearish_score += 1
        elif indicators.rsi_14 <= 30:
            bullish_score += 1
        elif indicators.rsi_14 >= 55:
            bullish_score += 1
        elif indicators.rsi_14 <= 45:
            bearish_score += 1

    if bullish_score > bearish_score:
        return ForecastDirection.bullish
    if bearish_score > bullish_score:
        return ForecastDirection.bearish
    return ForecastDirection.neutral


def _research_levels(price: float, atr: float, direction: ForecastDirection) -> tuple[float, float, float]:
    entry = round(price, 2)
    if direction == ForecastDirection.bearish:
        take_profit = max(price - (atr * 2), price * 0.5)
        stop_loss = price + atr
    elif direction == ForecastDirection.bullish:
        take_profit = price + (atr * 2)
        stop_loss = max(price - atr, price * 0.5)
    else:
        take_profit = price + atr
        stop_loss = max(price - atr, price * 0.5)
    return entry, round(take_profit, 2), round(stop_loss, 2)


def _usable_atr(indicators: TechnicalIndicators, latest_bar: DailyBar, price: float) -> float:
    if indicators.atr_14 is not None and indicators.atr_14 > 0:
        return indicators.atr_14
    return max(latest_bar.high - latest_bar.low, price * 0.005, 1.0)


def _technical_summary(
    price: float,
    latest_bar: DailyBar,
    indicators: TechnicalIndicators,
    direction: ForecastDirection,
) -> str:
    direction_text = {
        ForecastDirection.bullish: "看多",
        ForecastDirection.bearish: "看空",
        ForecastDirection.neutral: "震荡/中性",
    }[direction]
    parts = [
        f"当前报价 {price:.2f}，最新完成日线收盘 {latest_bar.close:.2f}，结构化方向为{direction_text}。",
    ]
    if indicators.sma_20 is not None:
        parts.append(f"SMA-20 为 {indicators.sma_20:.2f}。")
    if indicators.ema_12 is not None:
        parts.append(f"EMA-12 为 {indicators.ema_12:.2f}。")
    if indicators.rsi_14 is not None:
        parts.append(f"RSI-14 为 {indicators.rsi_14:.2f}。")
    if indicators.unavailable:
        parts.append(f"部分指标不可用：{', '.join(sorted(indicators.unavailable))}。")
    return "".join(parts)


def _risk_notes(latest_bar: DailyBar, indicators: TechnicalIndicators, atr: float) -> list[str]:
    notes = [f"ATR 参考值约为 {atr:.2f}，止损和止盈仅用于研究情景测算。"]
    daily_range = latest_bar.high - latest_bar.low
    if daily_range > atr * 1.5:
        notes.append("最新日线振幅明显高于 ATR 参考，需警惕波动放大。")
    if indicators.rsi_14 is not None and indicators.rsi_14 >= 70:
        notes.append("RSI 处于偏高区域，追多研究假设需要额外确认。")
    if indicators.rsi_14 is not None and indicators.rsi_14 <= 30:
        notes.append("RSI 处于偏低区域，追空研究假设需要额外确认。")
    if indicators.unavailable:
        notes.append("部分技术指标不可用，confidence 已按信息不足做保守处理。")
    return notes


def _technical_confidence(indicators: TechnicalIndicators, direction: ForecastDirection) -> float:
    available = 4 - len(indicators.unavailable)
    base = 0.45 + (available * 0.07)
    if direction == ForecastDirection.neutral:
        base -= 0.08
    return round(min(max(base, 0.25), 0.78), 2)


def _combined_confidence(agent_votes: list[AgentVote], indicators: TechnicalIndicators) -> float:
    if not agent_votes:
        return 0.35
    average = sum(vote.confidence for vote in agent_votes) / len(agent_votes)
    if indicators.unavailable:
        average -= 0.05
    return round(min(max(average, 0.2), 0.85), 2)


def _aggregate_agent_votes(agent_votes: list[AgentVote]) -> tuple[ForecastDirection, float]:
    if not agent_votes:
        return ForecastDirection.neutral, 0.35

    weighted_scores = {direction: 0.0 for direction in ForecastDirection}
    for vote in agent_votes:
        weighted_scores[vote.direction] += vote.confidence

    # 使用 confidence 加权得分决定方向；confidence_score 保留所有 agent 的平均置信度，避免单一高置信票吞掉分歧。
    direction = max(
        ForecastDirection,
        key=lambda candidate: (weighted_scores[candidate], candidate == ForecastDirection.neutral),
    )
    confidence_score = sum(vote.confidence for vote in agent_votes) / len(agent_votes)
    return direction, round(min(max(confidence_score, 0.2), 0.85), 2)


def _risk_vote_direction(direction: ForecastDirection, atr: float, price: float) -> ForecastDirection:
    if atr / price > 0.02:
        return ForecastDirection.neutral
    return direction


def _holding_period(direction: ForecastDirection, atr: float, price: float) -> str:
    if direction == ForecastDirection.neutral or atr / price > 0.015:
        return "1-3 个交易日，等待方向确认"
    return "3-7 个交易日，随每日收盘重新评估"


def _intraday_action(
    direction: ForecastDirection,
    entry_price: float,
    take_profit_price: float,
    stop_loss_price: float,
) -> str:
    if direction == ForecastDirection.bullish:
        return (
            f"研究情景偏多：关注 {entry_price:.2f} 附近的回踩确认，"
            f"止盈参考 {take_profit_price:.2f}，止损参考 {stop_loss_price:.2f}。"
        )
    if direction == ForecastDirection.bearish:
        return (
            f"研究情景偏空：关注 {entry_price:.2f} 附近的反弹承压，"
            f"止盈参考 {take_profit_price:.2f}，止损参考 {stop_loss_price:.2f}。"
        )
    return f"研究情景中性：关注 {entry_price:.2f} 附近区间反应，等待突破或跌破后再更新假设。"


def _long_term_action(direction: ForecastDirection) -> str:
    if direction == ForecastDirection.bullish:
        return "中期研究倾向保持多头观察，但需用后续日线收盘和宏观数据确认。"
    if direction == ForecastDirection.bearish:
        return "中期研究倾向保持防守或空头观察，但需用后续日线收盘和宏观数据确认。"
    return "中期研究维持观望，等待趋势指标和外部数据给出更清晰方向。"


def _existing_votes_without(state: WorkflowState, agent_name: str) -> list[AgentVote]:
    return [vote for vote in state.get("agent_votes", []) if vote.agent != agent_name]


def _remote_agent_response(state: WorkflowState, agent_name: str) -> tuple[AgentApiResponse | None, str | None]:
    settings = state.get("settings") or get_settings()
    if not settings.openai_base_url or not settings.openai_model or not settings.openai_api_key:
        return None, None

    # 只发送可验证的市场/指标上下文，不把 secret 或 settings 放进 payload。
    payload = _agent_payload(state, agent_name)
    transport = state.get("agent_http_transport")
    try:
        result = OpenAIAgentClient(
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            api_key=settings.openai_api_key.get_secret_value(),
            transport=transport,
        ).invoke_agent(agent_name, payload)
    except OpenAIClientError:
        return None, f"OpenAI-compatible {agent_name} agent 调用失败，已回退到 deterministic workflow 输出。"

    return AgentApiResponse.model_validate(result.model_dump()), None


def _merge_notes(base_notes: list[str] | None, extra_notes: list[str] | None) -> list[str]:
    merged: list[str] = []
    for note in [*(base_notes or []), *(extra_notes or [])]:
        if note not in merged:
            merged.append(note)
    return merged


def _append_note(notes: list[str] | None, note: str | None) -> list[str]:
    if note is None:
        return list(notes or [])
    return _merge_notes(notes, [note])


def _agent_payload(state: WorkflowState, agent_name: str) -> dict[str, object]:
    latest_bar = state.get("latest_bar")
    quote = state.get("quote")
    indicators = state.get("indicators")
    payload: dict[str, object] = {"agent": agent_name, "symbol": "XAUUSD"}
    if latest_bar:
        payload["latest_bar"] = latest_bar.model_dump(mode="json")
        payload["symbol"] = latest_bar.symbol
    if quote:
        payload["quote"] = quote.model_dump(mode="json")
        payload["symbol"] = quote.symbol
    if indicators:
        payload["indicators"] = indicators.model_dump(mode="json")
    return payload


def _input_summary(state: WorkflowState) -> dict[str, object]:
    latest_bar = state.get("latest_bar")
    quote = state.get("quote")
    return {
        "symbol": quote.symbol if quote else (latest_bar.symbol if latest_bar else "XAUUSD"),
        "daily_bar_date": latest_bar.date.isoformat() if latest_bar else None,
        "data_source": quote.data_source if quote else None,
        "data_timestamp": quote.data_timestamp.isoformat() if quote else None,
    }


def _required(state: WorkflowState, key: str) -> Any:
    if key not in state:
        raise ValueError(f"workflow state missing required key: {key}")
    return state[key]  # type: ignore[literal-required]
