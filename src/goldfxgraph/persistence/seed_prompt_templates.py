from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from goldfxgraph.persistence.database import SessionFactory
from goldfxgraph.persistence.models import PromptTemplateModel

DEFAULT_COMMITTEE_PROMPT_VERSION = "1.0.0"


def _seed_template(
    *,
    prompt_key: str,
    prompt_type: str,
    agent_name: str,
    node_name: str,
    prompt_text_en: str,
    prompt_text_zh: str,
    output_schema_ref: str,
    description: str,
    change_notes: str,
    variables_schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "prompt_key": prompt_key,
        "agent_name": agent_name,
        "node_name": node_name,
        "prompt_type": prompt_type,
        "version": DEFAULT_COMMITTEE_PROMPT_VERSION,
        "prompt_text_en": prompt_text_en,
        "prompt_text_zh": prompt_text_zh,
        "variables_schema": dict(variables_schema or {}),
        "output_schema_ref": output_schema_ref,
        "model_family": "openai:gpt-4.1",
        "is_active": True,
        "description": description,
        "change_notes": change_notes,
    }


def _opening_system_prompt(side_label_en: str, side_label_zh: str) -> tuple[str, str]:
    return (
        f"You are the {side_label_en} opening-case agent for the Trading Committee. "
        "Use only the evidence package, do not invent facts, and present the strongest "
        f"{side_label_en} thesis while naming the main weakness.",
        f"你是交易委员会的{side_label_zh}开场陈述代理。只依据 evidence package，不要编造事实；"
        f"要提出最强的{side_label_zh}论证，并点明主要弱点。",
    )


def _opening_user_prompt(side_label_zh: str) -> tuple[str, str]:
    return (
        "Evidence package:\n{evidence_package}\n\nWrite the opening case as structured analysis.",
        f"Evidence package：\n{{evidence_package}}\n\n请把{side_label_zh}开场陈述写成结构化分析。",
    )


def _rebuttal_system_prompt(side_label_en: str, side_label_zh: str) -> tuple[str, str]:
    return (
        f"You are the {side_label_en} rebuttal agent for the Trading Committee. "
        "Respond point by point to the opposing opening case, accept valid criticism, "
        "and state whether the plan changes.",
        f"你是交易委员会的{side_label_zh}反驳代理。请逐点回应对方开场陈述，接受有效批评，"
        "并说明计划是否调整。",
    )


def _rebuttal_user_prompt(side_label_zh: str) -> tuple[str, str]:
    return (
        "Opening cases:\n{opening_cases}\n\n"
        "Evidence package:\n{evidence_package}\n\n"
        "Write the rebuttal in structured form.",
        f"双方开场陈述：\n{{opening_cases}}\n\n"
        f"Evidence package：\n{{evidence_package}}\n\n"
        f"请写出{side_label_zh}反驳稿，要求结构化。",
    )


def _final_system_prompt(side_label_en: str, side_label_zh: str) -> tuple[str, str]:
    return (
        f"You are the {side_label_en} final-position agent for the Trading Committee. "
        "Decide whether to maintain, soften, or abandon the stance, and clearly explain the final confidence, "
        "plan adjustments, and abandon conditions.",
        f"你是交易委员会的{side_label_zh}最终立场代理。请判断是否坚持、缓和或放弃原观点，"
        "并清楚说明最终置信度、计划调整和放弃条件。",
    )


def _final_user_prompt(side_label_zh: str) -> tuple[str, str]:
    return (
        "Opening case:\n{opening_case}\n\n"
        "Rebuttal:\n{rebuttal}\n\n"
        "Evidence package:\n{evidence_package}\n\n"
        "Write the final position as structured analysis.",
        f"开场陈述：\n{{opening_case}}\n\n"
        f"反驳：\n{{rebuttal}}\n\n"
        f"Evidence package：\n{{evidence_package}}\n\n"
        f"请把{side_label_zh}最终立场写成结构化分析。",
    )


def _chair_system_prompt() -> tuple[str, str]:
    return (
        "You are the Trading Committee chair. You are an arbiter, not a summarizer. "
        "Choose the winning side, final bias, actionability, and the arguments to adopt or reject.",
        "你是交易委员会主席。你是仲裁者，不是摘要员。请选择获胜一方、最终偏向、可执行性，"
        "以及要采纳或拒绝的论点。",
    )


def _chair_user_prompt() -> tuple[str, str]:
    return (
        "Evidence package:\n{evidence_package}\n\n"
        "Opening cases:\n{opening_cases}\n\n"
        "Rebuttals:\n{rebuttals}\n\n"
        "Final positions:\n{final_positions}\n\n"
        "Produce the committee decision in structured form.",
        "Evidence package：\n{evidence_package}\n\n"
        "开场陈述：\n{opening_cases}\n\n"
        "反驳：\n{rebuttals}\n\n"
        "最终立场：\n{final_positions}\n\n"
        "请输出结构化的委员会裁定。",
    )


def _repair_system_prompt() -> tuple[str, str]:
    return (
        "You are the committee repair agent. Fix only validation errors and structural issues. "
        "Do not invent new market facts.",
        "你是委员会修复代理。只修复验证错误和结构问题，不要编造新的市场事实。",
    )


def _repair_user_prompt() -> tuple[str, str]:
    return (
        "Validation errors:\n{validation_errors}\n\n"
        "Committee decision:\n{committee_decision}\n\n"
        "Evidence package:\n{evidence_package}\n\n"
        "Return a repaired decision that satisfies the validator.",
        "验证错误：\n{validation_errors}\n\n"
        "委员会决策：\n{committee_decision}\n\n"
        "Evidence package：\n{evidence_package}\n\n"
        "请返回一个满足校验器的修复后决策。",
    )


DEFAULT_COMMITTEE_PROMPT_SEEDS: tuple[dict[str, Any], ...] = (
    _seed_template(
        prompt_key="trading_committee.bull_opening_case.system",
        prompt_type="system",
        agent_name="trading_committee_bull_opening_case",
        node_name="agent_bull_opening_case",
        prompt_text_en=_opening_system_prompt("bullish", "看多")[0],
        prompt_text_zh=_opening_system_prompt("bullish", "看多")[1],
        output_schema_ref="goldfxgraph.schemas.forecast.DebateCase",
        description="看多开场陈述的 system prompt。",
        change_notes="首次预置默认模板。",
    ),
    _seed_template(
        prompt_key="trading_committee.bull_opening_case.user",
        prompt_type="user",
        agent_name="trading_committee_bull_opening_case",
        node_name="agent_bull_opening_case",
        prompt_text_en=_opening_user_prompt("看多")[0],
        prompt_text_zh=_opening_user_prompt("看多")[1],
        output_schema_ref="goldfxgraph.schemas.forecast.DebateCase",
        description="看多开场陈述的 user prompt。",
        change_notes="首次预置默认模板。",
        variables_schema={"required": ["evidence_package"]},
    ),
    _seed_template(
        prompt_key="trading_committee.bear_opening_case.system",
        prompt_type="system",
        agent_name="trading_committee_bear_opening_case",
        node_name="agent_bear_opening_case",
        prompt_text_en=_opening_system_prompt("bearish", "看空")[0],
        prompt_text_zh=_opening_system_prompt("bearish", "看空")[1],
        output_schema_ref="goldfxgraph.schemas.forecast.DebateCase",
        description="看空开场陈述的 system prompt。",
        change_notes="首次预置默认模板。",
    ),
    _seed_template(
        prompt_key="trading_committee.bear_opening_case.user",
        prompt_type="user",
        agent_name="trading_committee_bear_opening_case",
        node_name="agent_bear_opening_case",
        prompt_text_en=_opening_user_prompt("看空")[0],
        prompt_text_zh=_opening_user_prompt("看空")[1],
        output_schema_ref="goldfxgraph.schemas.forecast.DebateCase",
        description="看空开场陈述的 user prompt。",
        change_notes="首次预置默认模板。",
        variables_schema={"required": ["evidence_package"]},
    ),
    _seed_template(
        prompt_key="trading_committee.bull_rebuttal.system",
        prompt_type="system",
        agent_name="trading_committee_bull_rebuttal",
        node_name="agent_bull_rebuttal",
        prompt_text_en=_rebuttal_system_prompt("bullish", "看多")[0],
        prompt_text_zh=_rebuttal_system_prompt("bullish", "看多")[1],
        output_schema_ref="goldfxgraph.schemas.forecast.DebateRebuttal",
        description="看多反驳的 system prompt。",
        change_notes="首次预置默认模板。",
    ),
    _seed_template(
        prompt_key="trading_committee.bull_rebuttal.user",
        prompt_type="user",
        agent_name="trading_committee_bull_rebuttal",
        node_name="agent_bull_rebuttal",
        prompt_text_en=_rebuttal_user_prompt("看多")[0],
        prompt_text_zh=_rebuttal_user_prompt("看多")[1],
        output_schema_ref="goldfxgraph.schemas.forecast.DebateRebuttal",
        description="看多反驳的 user prompt。",
        change_notes="首次预置默认模板。",
        variables_schema={"required": ["opening_cases", "evidence_package"]},
    ),
    _seed_template(
        prompt_key="trading_committee.bear_rebuttal.system",
        prompt_type="system",
        agent_name="trading_committee_bear_rebuttal",
        node_name="agent_bear_rebuttal",
        prompt_text_en=_rebuttal_system_prompt("bearish", "看空")[0],
        prompt_text_zh=_rebuttal_system_prompt("bearish", "看空")[1],
        output_schema_ref="goldfxgraph.schemas.forecast.DebateRebuttal",
        description="看空反驳的 system prompt。",
        change_notes="首次预置默认模板。",
    ),
    _seed_template(
        prompt_key="trading_committee.bear_rebuttal.user",
        prompt_type="user",
        agent_name="trading_committee_bear_rebuttal",
        node_name="agent_bear_rebuttal",
        prompt_text_en=_rebuttal_user_prompt("看空")[0],
        prompt_text_zh=_rebuttal_user_prompt("看空")[1],
        output_schema_ref="goldfxgraph.schemas.forecast.DebateRebuttal",
        description="看空反驳的 user prompt。",
        change_notes="首次预置默认模板。",
        variables_schema={"required": ["opening_cases", "evidence_package"]},
    ),
    _seed_template(
        prompt_key="trading_committee.bull_final_position.system",
        prompt_type="system",
        agent_name="trading_committee_bull_final_position",
        node_name="agent_bull_final_position",
        prompt_text_en=_final_system_prompt("bullish", "看多")[0],
        prompt_text_zh=_final_system_prompt("bullish", "看多")[1],
        output_schema_ref="goldfxgraph.schemas.forecast.FinalDebatePosition",
        description="看多最终立场的 system prompt。",
        change_notes="首次预置默认模板。",
    ),
    _seed_template(
        prompt_key="trading_committee.bull_final_position.user",
        prompt_type="user",
        agent_name="trading_committee_bull_final_position",
        node_name="agent_bull_final_position",
        prompt_text_en=_final_user_prompt("看多")[0],
        prompt_text_zh=_final_user_prompt("看多")[1],
        output_schema_ref="goldfxgraph.schemas.forecast.FinalDebatePosition",
        description="看多最终立场的 user prompt。",
        change_notes="首次预置默认模板。",
        variables_schema={"required": ["opening_case", "rebuttal", "evidence_package"]},
    ),
    _seed_template(
        prompt_key="trading_committee.bear_final_position.system",
        prompt_type="system",
        agent_name="trading_committee_bear_final_position",
        node_name="agent_bear_final_position",
        prompt_text_en=_final_system_prompt("bearish", "看空")[0],
        prompt_text_zh=_final_system_prompt("bearish", "看空")[1],
        output_schema_ref="goldfxgraph.schemas.forecast.FinalDebatePosition",
        description="看空最终立场的 system prompt。",
        change_notes="首次预置默认模板。",
    ),
    _seed_template(
        prompt_key="trading_committee.bear_final_position.user",
        prompt_type="user",
        agent_name="trading_committee_bear_final_position",
        node_name="agent_bear_final_position",
        prompt_text_en=_final_user_prompt("看空")[0],
        prompt_text_zh=_final_user_prompt("看空")[1],
        output_schema_ref="goldfxgraph.schemas.forecast.FinalDebatePosition",
        description="看空最终立场的 user prompt。",
        change_notes="首次预置默认模板。",
        variables_schema={"required": ["opening_case", "rebuttal", "evidence_package"]},
    ),
    _seed_template(
        prompt_key="trading_committee.chair.system",
        prompt_type="system",
        agent_name="trading_committee_chair",
        node_name="agent_trading_committee_chair",
        prompt_text_en=_chair_system_prompt()[0],
        prompt_text_zh=_chair_system_prompt()[1],
        output_schema_ref="goldfxgraph.schemas.forecast.CommitteeDecision",
        description="委员会主席裁定的 system prompt。",
        change_notes="首次预置默认模板。",
    ),
    _seed_template(
        prompt_key="trading_committee.chair.user",
        prompt_type="user",
        agent_name="trading_committee_chair",
        node_name="agent_trading_committee_chair",
        prompt_text_en=_chair_user_prompt()[0],
        prompt_text_zh=_chair_user_prompt()[1],
        output_schema_ref="goldfxgraph.schemas.forecast.CommitteeDecision",
        description="委员会主席裁定的 user prompt。",
        change_notes="首次预置默认模板。",
        variables_schema={
            "required": ["evidence_package", "opening_cases", "rebuttals", "final_positions"],
        },
    ),
    _seed_template(
        prompt_key="trading_committee.repair.system",
        prompt_type="system",
        agent_name="trading_committee_repair",
        node_name="agent_repair_committee_decision",
        prompt_text_en=_repair_system_prompt()[0],
        prompt_text_zh=_repair_system_prompt()[1],
        output_schema_ref="goldfxgraph.schemas.forecast.CommitteeDecision",
        description="委员会修复的 system prompt。",
        change_notes="首次预置默认模板。",
    ),
    _seed_template(
        prompt_key="trading_committee.repair.user",
        prompt_type="user",
        agent_name="trading_committee_repair",
        node_name="agent_repair_committee_decision",
        prompt_text_en=_repair_user_prompt()[0],
        prompt_text_zh=_repair_user_prompt()[1],
        output_schema_ref="goldfxgraph.schemas.forecast.CommitteeDecision",
        description="委员会修复的 user prompt。",
        change_notes="首次预置默认模板。",
        variables_schema={"required": ["validation_errors", "committee_decision", "evidence_package"]},
    ),
)

DEFAULT_COMMITTEE_PROMPT_KEYS: tuple[str, ...] = tuple(seed["prompt_key"] for seed in DEFAULT_COMMITTEE_PROMPT_SEEDS)


async def seed_default_committee_prompt_templates(session_factory: SessionFactory) -> int:
    written_at = datetime.now(UTC)
    async with session_factory.sessionmaker() as session:
        for seed in DEFAULT_COMMITTEE_PROMPT_SEEDS:
            await session.execute(
                update(PromptTemplateModel)
                .where(
                    PromptTemplateModel.prompt_key == seed["prompt_key"],
                    PromptTemplateModel.version != seed["version"],
                )
                .values(is_active=False, updated_at=written_at)
            )

            insert_statement = _build_insert_statement(session, seed, written_at)
            await session.execute(insert_statement)
        await session.commit()
    return len(DEFAULT_COMMITTEE_PROMPT_SEEDS)


def _build_insert_statement(
    session: Any,
    seed: Mapping[str, Any],
    written_at: datetime,
) -> Any:
    dialect_name = getattr(getattr(session, "bind", None), "dialect", None)
    dialect_name = getattr(dialect_name, "name", "")
    insert_builder = sqlite_insert if dialect_name == "sqlite" else postgres_insert
    row = {**seed, "created_at": written_at, "updated_at": written_at}
    insert_statement = insert_builder(PromptTemplateModel).values(row)
    return insert_statement.on_conflict_do_update(
        index_elements=[PromptTemplateModel.prompt_key, PromptTemplateModel.version],
        set_={
            "agent_name": insert_statement.excluded.agent_name,
            "node_name": insert_statement.excluded.node_name,
            "prompt_type": insert_statement.excluded.prompt_type,
            "prompt_text_en": insert_statement.excluded.prompt_text_en,
            "prompt_text_zh": insert_statement.excluded.prompt_text_zh,
            "variables_schema": insert_statement.excluded.variables_schema,
            "output_schema_ref": insert_statement.excluded.output_schema_ref,
            "model_family": insert_statement.excluded.model_family,
            "is_active": True,
            "description": insert_statement.excluded.description,
            "change_notes": insert_statement.excluded.change_notes,
            "updated_at": written_at,
        },
    )
