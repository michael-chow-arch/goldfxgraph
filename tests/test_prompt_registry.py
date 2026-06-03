from __future__ import annotations

import pytest

from goldfxgraph.persistence import create_session_factory, init_models
from goldfxgraph.persistence.models import PromptTemplateModel
from goldfxgraph.persistence.prompt_registry import (
    PromptTemplateNotFoundError,
    PromptTemplateService,
    PromptTemplateVariableError,
)
from goldfxgraph.persistence.seed_prompt_templates import (
    DEFAULT_COMMITTEE_PROMPT_VERSION,
    seed_default_committee_prompt_templates,
)

pytestmark = pytest.mark.asyncio


async def _insert_prompt_template(
    session_factory,
    *,
    prompt_key: str,
    version: str,
    is_active: bool,
    prompt_text_en: str,
    prompt_text_zh: str,
    variables_schema: dict[str, object] | None = None,
) -> PromptTemplateModel:
    async with session_factory.sessionmaker() as session:
        template = PromptTemplateModel(
            prompt_key=prompt_key,
            agent_name="trading_committee_bull",
            node_name="agent_bull_opening_case",
            prompt_type="opening_case",
            version=version,
            prompt_text_en=prompt_text_en,
            prompt_text_zh=prompt_text_zh,
            variables_schema=variables_schema or {},
            output_schema_ref="goldfxgraph.schemas.forecast.DebateCase",
            model_family="openai:gpt-4.1",
            is_active=is_active,
            description="测试模板",
            change_notes="初始版本",
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        return template


async def test_get_active_prompt_returns_active_version() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)

    await _insert_prompt_template(
        session_factory,
        prompt_key="committee.bull.opening_case",
        version="1.0.0",
        is_active=False,
        prompt_text_en="Old prompt for {topic}.",
        prompt_text_zh="旧提示词：{topic}。",
    )
    active_template = await _insert_prompt_template(
        session_factory,
        prompt_key="committee.bull.opening_case",
        version="1.1.0",
        is_active=True,
        prompt_text_en="Active prompt for {topic} with {tone}.",
        prompt_text_zh="当前提示词：{topic}，语气为{tone}。",
    )

    service = PromptTemplateService(session_factory)
    prompt = await service.get_active_prompt("committee.bull.opening_case")

    assert prompt.id == active_template.id
    assert prompt.prompt_key == "committee.bull.opening_case"
    assert prompt.version == "1.1.0"
    assert prompt.is_active is True
    assert prompt.prompt_text_en == "Active prompt for {topic} with {tone}."
    assert prompt.prompt_text_zh == "当前提示词：{topic}，语气为{tone}。"


async def test_validate_required_variables_raises_for_missing_placeholder() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)

    template = await _insert_prompt_template(
        session_factory,
        prompt_key="committee.bear.rebuttal",
        version="1.0.0",
        is_active=True,
        prompt_text_en="Counter {claim} with {evidence}.",
        prompt_text_zh="用{evidence}反驳{claim}。",
    )

    service = PromptTemplateService(session_factory)

    with pytest.raises(PromptTemplateVariableError) as exc_info:
        service.validate_required_variables(template, {"claim": "gold is weak"})

    assert exc_info.value.prompt_key == "committee.bear.rebuttal"
    assert exc_info.value.version == "1.0.0"
    assert exc_info.value.missing_variable_names == ("evidence",)


async def test_render_prompt_returns_runtime_and_maintenance_text_with_metadata() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)

    await _insert_prompt_template(
        session_factory,
        prompt_key="committee.chair.finalize",
        version="2.0.0",
        is_active=True,
        prompt_text_en="Decide on {bias} and {confidence}.",
        prompt_text_zh="根据{bias}和{confidence}做最终裁定。",
        variables_schema={"required": ["bias", "confidence"]},
    )

    service = PromptTemplateService(session_factory)
    rendered = await service.render_prompt(
        "committee.chair.finalize",
        {"bias": "bullish", "confidence": "0.72"},
    )

    assert rendered.prompt_key == "committee.chair.finalize"
    assert rendered.version == "2.0.0"
    assert rendered.runtime_text_en == "Decide on bullish and 0.72."
    assert rendered.maintenance_text_zh == "根据bullish和0.72做最终裁定。"
    assert rendered.rendered_variable_names == ("bias", "confidence")


async def test_get_active_prompt_rejects_inactive_version_when_no_active_exists() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)

    await _insert_prompt_template(
        session_factory,
        prompt_key="committee.bull.repair",
        version="1.0.0",
        is_active=False,
        prompt_text_en="Repair with {error}.",
        prompt_text_zh="用{error}修复。",
    )

    service = PromptTemplateService(session_factory)

    with pytest.raises(PromptTemplateNotFoundError) as exc_info:
        await service.get_active_prompt("committee.bull.repair")

    assert exc_info.value.prompt_key == "committee.bull.repair"


async def test_seeded_committee_prompt_templates_are_loadable_and_renderable() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    await seed_default_committee_prompt_templates(session_factory)

    service = PromptTemplateService(session_factory)

    chair_system = await service.get_active_prompt("trading_committee.chair.system")
    assert chair_system.version == DEFAULT_COMMITTEE_PROMPT_VERSION
    assert chair_system.is_active is True
    assert chair_system.prompt_type == "system"
    assert "仲裁者" in chair_system.prompt_text_zh

    rendered = await service.render_prompt(
        "trading_committee.repair.user",
        {
            "validation_errors": "missing target zone",
            "committee_decision": "committee decision payload",
            "evidence_package": "evidence package payload",
        },
    )

    assert rendered.prompt_key == "trading_committee.repair.user"
    assert rendered.version == DEFAULT_COMMITTEE_PROMPT_VERSION
    assert rendered.runtime_text_en.startswith("Validation errors:")
    assert "missing target zone" in rendered.runtime_text_en
    assert rendered.maintenance_text_zh.startswith("验证错误：")
    assert rendered.rendered_variable_names == (
        "validation_errors",
        "committee_decision",
        "evidence_package",
    )
