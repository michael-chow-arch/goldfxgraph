from __future__ import annotations

from sqlalchemy import select

from goldfxgraph.persistence.database import SessionFactory
from goldfxgraph.persistence.models import PromptTemplateModel

REQUIRED_ANALYSIS_PROMPT_KEYS: tuple[str, ...] = (
    "analysis.generic.system",
    "analysis.generic.user",
)

REQUIRED_COMMITTEE_PROMPT_KEYS: tuple[str, ...] = (
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

REQUIRED_PROMPT_KEYS: tuple[str, ...] = REQUIRED_ANALYSIS_PROMPT_KEYS + REQUIRED_COMMITTEE_PROMPT_KEYS


class PromptRegistryValidationError(RuntimeError):
    def __init__(self, missing_prompt_keys: tuple[str, ...]) -> None:
        self.missing_prompt_keys = missing_prompt_keys
        message = "missing required prompt templates: " + ", ".join(missing_prompt_keys)
        super().__init__(message)


async def validate_required_prompt_templates(session_factory: SessionFactory) -> int:
    async with session_factory.sessionmaker() as session:
        statement = (
            select(PromptTemplateModel.prompt_key)
            .where(
                PromptTemplateModel.prompt_key.in_(REQUIRED_PROMPT_KEYS),
                PromptTemplateModel.is_active.is_(True),
            )
        )
        result = await session.execute(statement)
        active_prompt_keys = {row[0] for row in result.all()}

    missing_prompt_keys = tuple(prompt_key for prompt_key in REQUIRED_PROMPT_KEYS if prompt_key not in active_prompt_keys)
    if missing_prompt_keys:
        raise PromptRegistryValidationError(missing_prompt_keys)
    return len(active_prompt_keys)
