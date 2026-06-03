from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from string import Formatter
from typing import Any

from sqlalchemy import select

from goldfxgraph.persistence.database import SessionFactory
from goldfxgraph.persistence.models import PromptTemplateModel


class PromptTemplateNotFoundError(LookupError):
    def __init__(self, prompt_key: str) -> None:
        self.prompt_key = prompt_key
        super().__init__(f"active prompt template not found for prompt_key={prompt_key!r}")


class PromptTemplateVariableError(ValueError):
    def __init__(
        self,
        prompt_key: str,
        version: str,
        missing_variable_names: tuple[str, ...],
    ) -> None:
        self.prompt_key = prompt_key
        self.version = version
        self.missing_variable_names = missing_variable_names
        message = (
            f"prompt template {prompt_key!r} version {version!r} is missing required variables: "
            f"{', '.join(missing_variable_names)}"
        )
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class PromptTemplateSnapshot:
    id: int
    prompt_key: str
    agent_name: str | None
    node_name: str | None
    prompt_type: str
    version: str
    prompt_text_en: str
    prompt_text_zh: str
    variables_schema: dict[str, Any]
    output_schema_ref: str | None
    model_family: str | None
    is_active: bool
    description: str | None
    change_notes: str | None
    created_at: datetime
    updated_at: datetime
    required_variable_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    prompt_key: str
    version: str
    prompt_type: str
    runtime_text_en: str
    maintenance_text_zh: str
    rendered_variable_names: tuple[str, ...]
    agent_name: str | None = None
    node_name: str | None = None
    model_family: str | None = None
    output_schema_ref: str | None = None
    is_active: bool | None = None


class PromptTemplateService:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def get_active_prompt(self, prompt_key: str) -> PromptTemplateSnapshot:
        normalized_prompt_key = _normalize_prompt_key(prompt_key)
        async with self._session_factory.sessionmaker() as session:
            statement = (
                select(PromptTemplateModel)
                .where(
                    PromptTemplateModel.prompt_key == normalized_prompt_key,
                    PromptTemplateModel.is_active.is_(True),
                )
                .order_by(PromptTemplateModel.updated_at.desc(), PromptTemplateModel.id.desc())
                .limit(1)
            )
            result = await session.execute(statement)
            model = result.scalars().first()
            if model is None:
                raise PromptTemplateNotFoundError(normalized_prompt_key)
            return _snapshot_from_model(model)

    def validate_required_variables(
        self,
        prompt_template: PromptTemplateModel | PromptTemplateSnapshot,
        variables: Mapping[str, Any],
    ) -> tuple[str, ...]:
        required_variable_names = _required_variable_names(prompt_template)
        missing_variable_names = tuple(name for name in required_variable_names if name not in variables)
        if missing_variable_names:
            raise PromptTemplateVariableError(
                prompt_template.prompt_key,
                prompt_template.version,
                missing_variable_names,
            )
        return required_variable_names

    async def render_prompt(self, prompt_key: str, variables: Mapping[str, Any]) -> RenderedPrompt:
        prompt_template = await self.get_active_prompt(prompt_key)
        rendered_variable_names = self.validate_required_variables(prompt_template, variables)
        runtime_text_en = _render_template(prompt_template.prompt_text_en, variables)
        maintenance_text_zh = _render_template(prompt_template.prompt_text_zh, variables)
        return RenderedPrompt(
            prompt_key=prompt_template.prompt_key,
            version=prompt_template.version,
            prompt_type=prompt_template.prompt_type,
            runtime_text_en=runtime_text_en,
            maintenance_text_zh=maintenance_text_zh,
            rendered_variable_names=rendered_variable_names,
            agent_name=prompt_template.agent_name,
            node_name=prompt_template.node_name,
            model_family=prompt_template.model_family,
            output_schema_ref=prompt_template.output_schema_ref,
            is_active=prompt_template.is_active,
        )


def _snapshot_from_model(model: PromptTemplateModel) -> PromptTemplateSnapshot:
    return PromptTemplateSnapshot(
        id=model.id,
        prompt_key=model.prompt_key,
        agent_name=model.agent_name,
        node_name=model.node_name,
        prompt_type=model.prompt_type,
        version=model.version,
        prompt_text_en=model.prompt_text_en,
        prompt_text_zh=model.prompt_text_zh,
        variables_schema=dict(model.variables_schema),
        output_schema_ref=model.output_schema_ref,
        model_family=model.model_family,
        is_active=model.is_active,
        description=model.description,
        change_notes=model.change_notes,
        created_at=model.created_at,
        updated_at=model.updated_at,
        required_variable_names=_required_variable_names_from_texts(model.prompt_text_en, model.prompt_text_zh),
    )


def _required_variable_names(
    prompt_template: PromptTemplateModel | PromptTemplateSnapshot,
) -> tuple[str, ...]:
    if isinstance(prompt_template, PromptTemplateSnapshot):
        return prompt_template.required_variable_names
    return _required_variable_names_from_texts(prompt_template.prompt_text_en, prompt_template.prompt_text_zh)


def _required_variable_names_from_texts(*texts: str) -> tuple[str, ...]:
    required_variable_names: list[str] = []
    seen_names: set[str] = set()
    for text in texts:
        for field_name in _extract_field_names(text):
            if field_name in seen_names:
                continue
            seen_names.add(field_name)
            required_variable_names.append(field_name)
    return tuple(required_variable_names)


def _extract_field_names(text: str) -> tuple[str, ...]:
    formatter = Formatter()
    field_names: list[str] = []
    for _literal_text, field_name, _format_spec, _conversion in formatter.parse(text):
        if field_name is None:
            continue
        if not field_name:
            raise ValueError("prompt placeholders must use named variables")
        if any(token in field_name for token in (".", "[", "]")):
            raise ValueError(f"unsupported prompt placeholder: {field_name!r}")
        field_names.append(field_name)
    return tuple(field_names)


def _render_template(template: str, variables: Mapping[str, Any]) -> str:
    return template.format_map(dict(variables))


def _normalize_prompt_key(prompt_key: str) -> str:
    normalized_prompt_key = prompt_key.strip()
    if not normalized_prompt_key:
        raise ValueError("prompt_key must not be empty")
    return normalized_prompt_key
