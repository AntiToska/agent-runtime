from unittest.mock import MagicMock

import pytest
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

from agent_runtime.model_client import DeepSeekClient


def test_chat_forwards_configuration_and_returns_response() -> None:
    sdk_client = MagicMock(spec=OpenAI)
    sdk_client.chat = MagicMock()
    client = DeepSeekClient(sdk_client, "configured-model")
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": "hello"}]
    tools: list[ChatCompletionToolParam] = []

    response = client.chat(messages, tools)

    sdk_client.chat.completions.create.assert_called_once_with(
        model="configured-model",
        messages=messages,
        tools=tools,
        tool_choice="auto",
        extra_body={"thinking": {"type": "disabled"}},
    )
    assert response is sdk_client.chat.completions.create.return_value
    sdk_client.close.assert_not_called()


def test_chat_propagates_request_failure() -> None:
    sdk_client = MagicMock(spec=OpenAI)
    sdk_client.chat = MagicMock()
    sdk_client.chat.completions.create.side_effect = RuntimeError("request failed")

    with pytest.raises(RuntimeError, match="request failed"):
        DeepSeekClient(sdk_client, "test-model").chat([], [])

    sdk_client.chat.completions.create.assert_called_once()
