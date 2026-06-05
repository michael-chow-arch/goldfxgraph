import json

import httpx
import pytest

from goldfxgraph.llm.openai_client import OpenAIAgentClient, OpenAIClientError
from goldfxgraph.llm.openai_client import OpenAIAgentResult

TEST_AGENT_BASE_URL = "https://example.test/v1"


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
        base_url=TEST_AGENT_BASE_URL,
        model="gpt-4.1-mini",
        api_key="super-secret-key",
        transport=httpx.MockTransport(handler),
    )

    result = client.invoke_messages(
        agent_name="technical",
        messages=[
            {"role": "system", "content": "你是technical分析师，请用简体中文回答。"},
            {"role": "user", "content": '{"agent_name":"technical","symbol":"XAUUSD","latest_bar":{"close":2345.6}}'},
        ],
        output_model=OpenAIAgentResult,
    )

    assert result.summary == "技术面偏多。"
    assert result.direction.value == "bullish"
    assert result.confidence == pytest.approx(0.74)
    assert result.risk_notes == ["波动率上升"]

    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == f"{TEST_AGENT_BASE_URL}/chat/completions"
    assert request.headers["Authorization"] == "Bearer super-secret-key"

    payload = request.read().decode("utf-8")
    body = json.loads(payload)
    assert "super-secret-key" not in payload
    assert body["model"] == "gpt-4.1-mini"
    assert "简体中文" in body["messages"][0]["content"]
    assert "technical" in body["messages"][1]["content"]


def test_openai_client_rejects_non_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json", request=request)

    client = OpenAIAgentClient(
        base_url=TEST_AGENT_BASE_URL,
        model="gpt-4.1-mini",
        api_key="super-secret-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(OpenAIClientError, match="returned invalid JSON"):
        client.invoke_messages(
            agent_name="macro",
            messages=[{"role": "system", "content": "macro"}, {"role": "user", "content": '{"symbol":"XAUUSD"}'}],
            output_model=OpenAIAgentResult,
        )


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
        base_url=TEST_AGENT_BASE_URL,
        model="gpt-4.1-mini",
        api_key="super-secret-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(OpenAIClientError, match="returned invalid structured result"):
        client.invoke_messages(
            agent_name="news",
            messages=[{"role": "system", "content": "news"}, {"role": "user", "content": '{"symbol":"XAUUSD"}'}],
            output_model=OpenAIAgentResult,
        )


def test_openai_client_wraps_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "Authorization is wrong"}}, request=request)

    client = OpenAIAgentClient(
        base_url=TEST_AGENT_BASE_URL,
        model="gpt-4.1-mini",
        api_key="super-secret-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(OpenAIClientError, match="HTTP 400"):
        client.invoke_messages(
            agent_name="technical",
            messages=[{"role": "system", "content": "technical"}, {"role": "user", "content": '{"symbol":"XAUUSD"}'}],
            output_model=OpenAIAgentResult,
        )


def test_openai_client_includes_request_error_chain_in_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = OpenAIAgentClient(
        base_url=TEST_AGENT_BASE_URL,
        model="gpt-4.1-mini",
        api_key="super-secret-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(OpenAIClientError, match="ConnectError: connection refused"):
        client.invoke_messages(
            agent_name="news",
            messages=[{"role": "system", "content": "news"}, {"role": "user", "content": '{"symbol":"XAUUSD"}'}],
            output_model=OpenAIAgentResult,
        )


def test_openai_client_normalizes_string_risk_notes_to_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary":"技术面中性。","direction":"neutral",'
                                '"confidence":0.51,"risk_notes":"等待宏观数据确认。"}'
                            )
                        }
                    }
                ]
            },
            request=request,
        )

    client = OpenAIAgentClient(
        base_url=TEST_AGENT_BASE_URL,
        model="gpt-4.1-mini",
        api_key="super-secret-key",
        transport=httpx.MockTransport(handler),
    )

    result = client.invoke_messages(
        agent_name="technical",
        messages=[{"role": "system", "content": "technical"}, {"role": "user", "content": '{"symbol":"XAUUSD"}'}],
        output_model=OpenAIAgentResult,
    )

    assert result.risk_notes == ["等待宏观数据确认。"]


def test_openai_client_normalizes_conditional_direction_to_neutral() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary":"条件式方向判断。",'
                                '"direction":"bullish_above_2325_bearish_below_2300",'
                                '"confidence":0.63,"risk_notes":["等待突破确认"]}'
                            )
                        }
                    }
                ]
            },
            request=request,
        )

    client = OpenAIAgentClient(
        base_url=TEST_AGENT_BASE_URL,
        model="gpt-4.1-mini",
        api_key="super-secret-key",
        transport=httpx.MockTransport(handler),
    )

    result = client.invoke_messages(
        agent_name="technical",
        messages=[{"role": "system", "content": "technical"}, {"role": "user", "content": '{"symbol":"XAUUSD"}'}],
        output_model=OpenAIAgentResult,
    )

    assert result.direction.value == "neutral"
