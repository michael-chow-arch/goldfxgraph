from __future__ import annotations

from collections.abc import Iterable
from typing import Any
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from goldfxgraph.persistence.database import SessionFactory
from goldfxgraph.persistence.models import ExternalSourceModel, PromptTemplateModel

TEST_AGENT_MODEL = "gpt-4.1-mini"
TEST_AGENT_BASE_URL = "https://example.test/v1"
TEST_AGENT_API_KEY = "secret-token"
TEST_EXTERNAL_BASE_URL = "https://example.test"
TEST_EXTERNAL_RSS_BASE_URL = "https://example.test/rss"
TEST_EXTERNAL_DATA_BASE_URL = "https://example.test/data"
TEST_TRADINGVIEW_BASE_URL = "https://example.test/tradingview"
TEST_TRADINGVIEW_SOCKET_URL = "wss://example.test/tradingview/socket"
TEST_TRADINGVIEW_ORIGIN = "https://example.test"

TRADINGVIEW_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

REQUIRED_ANALYSIS_PROMPT_KEYS = (
    "analysis.generic.system",
    "analysis.generic.user",
)

REQUIRED_COMMITTEE_PROMPT_KEYS = (
    "trading_committee.bull_opening_case.system",
    "trading_committee.bull_opening_case.user",
    "trading_committee.bear_opening_case.system",
    "trading_committee.bear_opening_case.user",
    "trading_committee.bull_rebuttal.system",
    "trading_committee.bull_rebuttal.user",
    "trading_committee.bear_rebuttal.system",
    "trading_committee.bear_rebuttal.user",
    "trading_committee.bull_final_position.system",
    "trading_committee.bull_final_position.user",
    "trading_committee.bear_final_position.system",
    "trading_committee.bear_final_position.user",
    "trading_committee.chair.system",
    "trading_committee.chair.user",
    "trading_committee.repair.system",
    "trading_committee.repair.user",
)


async def seed_required_prompt_templates(session_factory: SessionFactory) -> None:
    async with session_factory.sessionmaker() as session:
        session.add_all(_prompt_template_models())
        await session.commit()


async def seed_required_external_sources(session_factory: SessionFactory) -> None:
    async with session_factory.sessionmaker() as session:
        session.add_all(_external_source_models())
        await session.commit()


async def seed_runtime_registry(session_factory: SessionFactory) -> None:
    await seed_required_prompt_templates(session_factory)
    await seed_required_external_sources(session_factory)


def _prompt_template_models() -> list[PromptTemplateModel]:
    models: list[PromptTemplateModel] = []

    models.extend(
        [
            _prompt_template(
                prompt_key="analysis.generic.system",
                agent_name="analysis",
                node_name="agent_generic_analysis",
                prompt_type="system",
                prompt_text_en="You are the {agent_name} research analyst. Respond in 简体中文 and return JSON only.",
                prompt_text_zh="你是{agent_name}研究分析师。请只返回 JSON，并使用简体中文。",
            ),
            _prompt_template(
                prompt_key="analysis.generic.user",
                agent_name="analysis",
                node_name="agent_generic_analysis",
                prompt_type="user",
                prompt_text_en='{{"agent_name":"{agent_name}","payload":{payload_json}}}',
                prompt_text_zh='{{"agent_name":"{agent_name}","payload":{payload_json}}}',
            ),
        ]
    )

    prompt_specs: dict[str, tuple[str, tuple[str, ...]]] = {
        "bull_opening_case": ("evidence_package",),
        "bear_opening_case": ("evidence_package",),
        "bull_rebuttal": ("opening_cases", "evidence_package"),
        "bear_rebuttal": ("opening_cases", "evidence_package"),
        "bull_final_position": ("opening_case", "rebuttal", "evidence_package"),
        "bear_final_position": ("opening_case", "rebuttal", "evidence_package"),
        "chair": ("evidence_package", "opening_cases", "rebuttals"),
        "repair": ("validation_errors", "committee_decision", "evidence_package"),
    }

    for role, required_variables in prompt_specs.items():
        system_key = f"trading_committee.{role}.system"
        user_key = f"trading_committee.{role}.user"
        prompt_role_name = role.replace("_", " ")
        models.append(
            _prompt_template(
                prompt_key=system_key,
                agent_name="trading_committee",
                node_name=f"agent_{role}",
                prompt_type="system",
                prompt_text_en=(
                    f"You are the {prompt_role_name} committee system prompt. "
                    "Use only the evidence package and related structured inputs."
                ),
                prompt_text_zh=(
                    f"你是{prompt_role_name}委员会系统提示词。"
                    "只能使用提供的结构化输入，不要编造事实。"
                ),
            )
        )
        user_template_en = _committee_user_template(role, required_variables, language="en")
        user_template_zh = _committee_user_template(role, required_variables, language="zh")
        models.append(
            _prompt_template(
                prompt_key=user_key,
                agent_name="trading_committee",
                node_name=f"agent_{role}",
                prompt_type="user",
                prompt_text_en=user_template_en,
                prompt_text_zh=user_template_zh,
            )
        )

    return models


def _committee_user_template(role: str, required_variables: tuple[str, ...], *, language: str) -> str:
    if language == "zh":
        if role in {"bull_opening_case", "bear_opening_case"}:
            return "证据包：{evidence_package}"
        if role in {"bull_rebuttal", "bear_rebuttal"}:
            return "开场：{opening_cases}\n证据包：{evidence_package}"
        if role in {"bull_final_position", "bear_final_position"}:
            return "开场：{opening_case}\n反驳：{rebuttal}\n证据包：{evidence_package}"
        if role == "chair":
            return "证据包：{evidence_package}\n开场：{opening_cases}\n反驳：{rebuttals}"
        if role == "repair":
            return "验证错误：{validation_errors}\n委员会决策：{committee_decision}\n证据包：{evidence_package}"
    else:
        if role in {"bull_opening_case", "bear_opening_case"}:
            return "Evidence package: {evidence_package}"
        if role in {"bull_rebuttal", "bear_rebuttal"}:
            return "Opening cases: {opening_cases}\nEvidence package: {evidence_package}"
        if role in {"bull_final_position", "bear_final_position"}:
            return "Opening case: {opening_case}\nRebuttal: {rebuttal}\nEvidence package: {evidence_package}"
        if role == "chair":
            return "Evidence package: {evidence_package}\nOpening cases: {opening_cases}\nRebuttals: {rebuttals}"
        if role == "repair":
            return "Validation errors: {validation_errors}\nCommittee decision: {committee_decision}\nEvidence package: {evidence_package}"
    raise ValueError(f"unsupported committee role: {role}; required={required_variables}")


def _prompt_template(
    *,
    prompt_key: str,
    agent_name: str | None,
    node_name: str | None,
    prompt_type: str,
    prompt_text_en: str,
    prompt_text_zh: str,
) -> PromptTemplateModel:
    return PromptTemplateModel(
        prompt_key=prompt_key,
        agent_name=agent_name,
        node_name=node_name,
        prompt_type=prompt_type,
        version="1.0.0",
        prompt_text_en=prompt_text_en,
        prompt_text_zh=prompt_text_zh,
        variables_schema={},
        output_schema_ref="goldfxgraph.schemas.forecast.DebateCase",
        model_family="openai:gpt-4.1",
        is_active=True,
        description="测试模板",
        change_notes="测试数据",
    )


def _external_source_models() -> list[ExternalSourceModel]:
    return [
        _external_source(
            source_key="llm.openai.analysis",
            source_type="llm",
            endpoint_url=TEST_AGENT_BASE_URL,
            request_config={
                "model": TEST_AGENT_MODEL,
                "api_key": TEST_AGENT_API_KEY,
                "timeout": 20,
            },
        ),
        _external_source(
            source_key="tradingview.current_quote",
            source_type="market_data",
            endpoint_url=f"{TEST_TRADINGVIEW_BASE_URL}/symbols/XAUUSD?exchange=FX",
            request_config={
                "socket_url": TEST_TRADINGVIEW_SOCKET_URL,
                "socket_from": "symbols/XAUUSD/",
                "auth": "unauthorized_user_token",
                "origin": TEST_TRADINGVIEW_ORIGIN,
                "user_agent": TRADINGVIEW_USER_AGENT,
                "symbol": "FX:XAUUSD",
                "source_name": "TradingView",
            },
        ),
        _external_source(
            source_key="tradingview.history",
            source_type="market_data",
            endpoint_url=f"{TEST_TRADINGVIEW_BASE_URL}/symbols/XAUUSD?exchange=FX",
            request_config={
                "http_url": f"{TEST_TRADINGVIEW_BASE_URL}/history",
                "ws_url": TEST_TRADINGVIEW_SOCKET_URL,
                "origin": TEST_TRADINGVIEW_ORIGIN,
                "user_agent": TRADINGVIEW_USER_AGENT,
                "auth_token": "unauthorized_user_token",
                "chart_symbol": "FX:XAUUSD",
                "chart_symbol_alias": "symbol_1",
                "chart_timezone": "Etc/UTC",
                "session_prefix": "cs_",
                "session_path": "symbols/XAUUSD/",
                "symbol": "XAUUSD",
                "source_name": "TradingView",
            },
        ),
        _external_source(
            source_key="newsflow.cnbc_markets",
            source_type="rss",
            endpoint_url=f"{TEST_EXTERNAL_RSS_BASE_URL}/cnbc/markets.xml",
            request_config={"source_name": "CNBC Markets"},
        ),
        _external_source(
            source_key="newsflow.marketwatch_top_stories",
            source_type="rss",
            endpoint_url=f"{TEST_EXTERNAL_RSS_BASE_URL}/marketwatch/topstories.xml",
            request_config={"source_name": "MarketWatch Top Stories"},
        ),
        _external_source(
            source_key="newsflow.google_news_gold",
            source_type="rss",
            endpoint_url=f"{TEST_EXTERNAL_RSS_BASE_URL}/google-news/gold.xml",
            request_config={"source_name": "Google News Gold"},
        ),
        _external_source(
            source_key="newsflow.google_news_rates",
            source_type="rss",
            endpoint_url=f"{TEST_EXTERNAL_RSS_BASE_URL}/google-news/rates.xml",
            request_config={"source_name": "Google News Rates"},
        ),
        _external_source(
            source_key="macro.fred.dollar_index",
            source_type="csv",
            endpoint_url=f"{TEST_EXTERNAL_DATA_BASE_URL}/fred/dollar-index.csv",
            request_config={},
        ),
        _external_source(
            source_key="macro.fred.real_rates",
            source_type="csv",
            endpoint_url=f"{TEST_EXTERNAL_DATA_BASE_URL}/fred/real-rates.csv",
            request_config={},
        ),
        _external_source(
            source_key="macro.cftc.gold_commitments",
            source_type="csv",
            endpoint_url=f"{TEST_EXTERNAL_DATA_BASE_URL}/cftc/gold-commitments.csv",
            request_config={
                "params": {
                    "$where": "commodity_name='GOLD'",
                    "$order": "report_date_as_yyyy_mm_dd DESC",
                    "$limit": 2,
                }
            },
        ),
        _external_source(
            source_key="alt.pizzint.watch",
            source_type="html",
            endpoint_url=f"{TEST_EXTERNAL_BASE_URL}/pizzint.watch/",
            request_config={"source_name": "Pizzint Watch"},
        ),
        _external_source(
            source_key="alt.polymarket.zh",
            source_type="html",
            endpoint_url=f"{TEST_EXTERNAL_BASE_URL}/polymarket/gold",
            request_config={"source_name": "Polymarket"},
        ),
    ]


def _external_source(
    *,
    source_key: str,
    source_type: str,
    endpoint_url: str,
    request_config: dict[str, Any],
) -> ExternalSourceModel:
    return ExternalSourceModel(
        source_key=source_key,
        source_type=source_type,
        endpoint_url=endpoint_url,
        request_config=request_config,
        version="1.0.0",
        is_active=True,
        description="测试外部源",
        change_notes="测试数据",
    )
