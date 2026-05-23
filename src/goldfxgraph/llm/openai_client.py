from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

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
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        request_payload = {
            "model": self._model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 GoldFXGraph 的分析 agent，名称为 "
                        f"{agent_name}。请只返回一个 JSON object，"
                        "字段必须包含 summary、direction、confidence、risk_notes。"
                        "所有自然语言字段必须使用简体中文，"
                        "direction 只能使用 bullish、bearish、neutral。"
                        "risk_notes 必须是字符串数组。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "agent_name": agent_name,
                            "payload": payload,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
        }
        client_kwargs: dict[str, Any] = {"timeout": 10}
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
        except httpx.HTTPError as exc:
            raise OpenAIClientError(f"OpenAI-compatible request failed for {agent_name}") from exc
        except JSONDecodeError as exc:
            raise OpenAIClientError(f"OpenAI-compatible response returned invalid JSON for {agent_name}") from exc

        content = self._extract_message_content(data, agent_name)
        structured_payload = self._parse_content_json(content, agent_name)
        structured_payload = self._normalize_structured_payload(structured_payload)

        try:
            return OpenAIAgentResult.model_validate(structured_payload)
        except ValidationError as exc:
            raise OpenAIClientError(
                f"OpenAI-compatible response returned invalid structured result for {agent_name}"
            ) from exc

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
