from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, Field, ValidationError

from goldfxgraph.schemas.forecast import ForecastDirection


class OpenAIClientError(RuntimeError):
    """OpenAI-compatible client failure."""


class OpenAIAgentResult(BaseModel):
    summary: str
    direction: ForecastDirection
    confidence: float = Field(ge=0, le=1)
    risk_notes: list[str] = Field(default_factory=list)


TStructuredModel = TypeVar("TStructuredModel", bound=BaseModel)


class OpenAIAgentClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._transport = transport

    def invoke_agent(self, agent_name: str, payload: dict[str, Any]) -> OpenAIAgentResult:
        system_prompt = (
            "你是 GoldFXGraph 的分析 agent，名称为 "
            f"{agent_name}。请只返回一个 JSON object，"
            "字段必须包含 summary、direction、confidence、risk_notes。"
            "所有自然语言字段必须使用简体中文，"
            "如果 payload 中存在 title_cn、source_cn、summary_cn 等中文翻译字段，必须优先使用，"
            "尤其在 news 与 market_sentiment 场景中不得直接输出英文新闻标题或英文市场标题作为摘要主体，"
            "如果 payload 中包含 newsflow_inputs 或 polymarket_inputs，请优先引用其中的中文标题、"
            "中文来源与中文摘要，"
            "direction 只能使用 bullish、bearish、neutral。"
            "risk_notes 必须是字符串数组。"
        )
        user_prompt = json.dumps(
            {
                "agent_name": agent_name,
                "payload": payload,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return self.invoke_prompted_model(
            agent_name=agent_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_model=OpenAIAgentResult,
        )

    def invoke_prompted_model(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        output_model: type[TStructuredModel],
    ) -> TStructuredModel:
        data = self._post_chat_completions(
            agent_name,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = self._extract_message_content(data, agent_name)
        structured_payload = self._parse_content_json(content, agent_name)
        if output_model is OpenAIAgentResult:
            structured_payload = self._normalize_structured_payload(structured_payload)

        try:
            return output_model.model_validate(structured_payload)
        except ValidationError as exc:
            raise OpenAIClientError(
                f"OpenAI-compatible response returned invalid structured result for {agent_name}"
            ) from exc

    def _post_chat_completions(self, agent_name: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        request_payload = {
            "model": self._model,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }
        client_kwargs: dict[str, Any] = {"timeout": 20}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        try:
            with httpx.Client(**client_kwargs) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    json=request_payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            response_text = exc.response.text.strip()
            response_excerpt = response_text[:300]
            suffix = f": {response_excerpt}" if response_excerpt else ""
            raise OpenAIClientError(
                f"OpenAI-compatible request failed for {agent_name} with HTTP {exc.response.status_code}{suffix}"
            ) from exc
        except httpx.HTTPError as exc:
            detail = _format_exception_chain(exc)
            raise OpenAIClientError(f"OpenAI-compatible request failed for {agent_name}: {detail}") from exc
        except JSONDecodeError as exc:
            raise OpenAIClientError(f"OpenAI-compatible response returned invalid JSON for {agent_name}") from exc

        if not isinstance(data, dict):
            raise OpenAIClientError(f"OpenAI-compatible response returned invalid JSON for {agent_name}")
        return data

    @staticmethod
    def _extract_message_content(data: Any, agent_name: str) -> str | dict[str, Any]:
        if not isinstance(data, dict):
            raise OpenAIClientError(f"OpenAI-compatible response returned invalid JSON for {agent_name}")

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OpenAIClientError(f"OpenAI-compatible response returned invalid JSON for {agent_name}")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise OpenAIClientError(f"OpenAI-compatible response returned invalid JSON for {agent_name}")

        message = first_choice.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise OpenAIClientError(f"OpenAI-compatible response returned invalid JSON for {agent_name}")

        content = message["content"]
        if isinstance(content, dict):
            return content
        if isinstance(content, str):
            return content

        raise OpenAIClientError(f"OpenAI-compatible response returned invalid JSON for {agent_name}")

    @staticmethod
    def _parse_content_json(content: str | dict[str, Any], agent_name: str) -> dict[str, Any]:
        if isinstance(content, dict):
            return content

        try:
            parsed = json.loads(content)
        except JSONDecodeError as exc:
            raise OpenAIClientError(f"OpenAI-compatible response returned invalid JSON for {agent_name}") from exc

        if not isinstance(parsed, dict):
            raise OpenAIClientError(f"OpenAI-compatible response returned invalid structured result for {agent_name}")

        return parsed

    @staticmethod
    def _normalize_structured_payload(payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)

        risk_notes = normalized.get("risk_notes")
        if isinstance(risk_notes, str):
            normalized["risk_notes"] = [risk_notes]
        elif risk_notes is None:
            normalized["risk_notes"] = []

        direction = normalized.get("direction")
        if isinstance(direction, str):
            lowered = direction.strip().lower()
            matched = [keyword for keyword in ("bullish", "bearish", "neutral") if keyword in lowered]
            if len(matched) == 1:
                normalized["direction"] = matched[0]
            elif len(matched) > 1:
                normalized["direction"] = "neutral"

        return normalized


def _format_exception_chain(exc: BaseException) -> str:
    parts: list[str] = []
    current: BaseException | None = exc
    while current is not None:
        label = type(current).__name__
        message = str(current).strip()
        if message:
            parts.append(f"{label}: {message}")
        else:
            parts.append(label)
        current = current.__cause__ if isinstance(current.__cause__, BaseException) else None

    return " | ".join(parts)
