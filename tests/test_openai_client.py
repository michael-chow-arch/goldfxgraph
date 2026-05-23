import json

import httpx
import pytest

from goldfxgraph.llm.openai_client import OpenAIAgentClient, OpenAIClientError


def test_openai_client_sends_bearer_header_and_parses_structured_result() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary":"技术面偏多。","direction":"bullish",'
                                '"confidence":0.74,"risk_notes":["波动率上升"]}'
                            )
                        }
                    }
                ]
            },
            request=request,
        )

    client = OpenAIAgentClient(
        base_url="https://api.zhizengzeng.com/v1",
        model="gpt-4.1-mini",
        api_key="super-secret-key",
        transport=httpx.MockTransport(handler),
    )

    result = client.invoke_agent(
        "technical",
        {
            "symbol": "XAUUSD",
            "latest_bar": {"close": 2345.6},
        },
    )

    assert result.summary == "技术面偏多。"
    assert result.direction.value == "bullish"
    assert result.confidence == pytest.approx(0.74)
    assert result.risk_notes == ["波动率上升"]

    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://api.zhizengzeng.com/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer super-secret-key"

    payload = request.read().decode("utf-8")
    body = json.loads(payload)
    assert "super-secret-key" not in payload
    assert body["model"] == "gpt-4.1-mini"
    assert "technical" in body["messages"][1]["content"]


def test_openai_client_rejects_non_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json", request=request)

    client = OpenAIAgentClient(
        base_url="https://api.zhizengzeng.com/v1",
        model="gpt-4.1-mini",
        api_key="super-secret-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(OpenAIClientError, match="returned invalid JSON"):
        client.invoke_agent("macro", {"symbol": "XAUUSD"})


def test_openai_client_rejects_invalid_structured_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"summary":"结构不完整","direction":"up","confidence":1.4,"risk_notes":"bad"}'
                        }
                    }
                ]
            },
            request=request,
        )

    client = OpenAIAgentClient(
        base_url="https://api.zhizengzeng.com/v1",
        model="gpt-4.1-mini",
        api_key="super-secret-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(OpenAIClientError, match="returned invalid structured result"):
        client.invoke_agent("news", {"symbol": "XAUUSD"})


def test_openai_client_wraps_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "service unavailable"}, request=request)

    client = OpenAIAgentClient(
        base_url="https://api.zhizengzeng.com/v1",
        model="gpt-4.1-mini",
        api_key="super-secret-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(OpenAIClientError, match="request failed for technical"):
        client.invoke_agent("technical", {"symbol": "XAUUSD"})
