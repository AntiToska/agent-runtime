import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from openai.types.chat import ChatCompletion

from agent_runtime.model_client import main


def completion(message: dict[str, Any]) -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "test-response",
            "object": "chat.completion",
            "created": 0,
            "model": "test-model",
            "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
        }
    )


@pytest.mark.parametrize(
    ("arguments", "expected_code"),
    [
        ('{"a":12,"b":30}', None),
        ("not json", "INVALID_ARGUMENTS"),
        ("[]", "INVALID_ARGUMENTS"),
        ('{"a":"12","b":30}', "INVALID_ARGUMENTS"),
    ],
)
def test_tool_results_are_sent_with_matching_ids(
    arguments: str, expected_code: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    calls = [
        {
            "id": "call-first",
            "type": "function",
            "function": {"name": "add", "arguments": arguments},
        },
        {
            "id": "call-second",
            "type": "function",
            "function": {"name": "add", "arguments": '{"a":1,"b":2}'},
        },
    ]
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        completion({"role": "assistant", "content": None, "tool_calls": calls}),
        completion({"role": "assistant", "content": "Done"}),
    ]
    with patch("agent_runtime.model_client.OpenAI") as factory:
        factory.return_value.__enter__.return_value = client
        main()

    requests = client.chat.completions.create.call_args_list
    assert len(requests) == 2
    assert len(requests[0].kwargs["messages"]) == 1
    messages = requests[1].kwargs["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant", "tool", "tool"]
    assert messages[1]["tool_calls"] == calls
    assert messages[2]["tool_call_id"] == "call-first"
    assert messages[3]["tool_call_id"] == "call-second"
    first_result = json.loads(messages[2]["content"])
    if expected_code is None:
        assert first_result == {"ok": True, "data": 42, "error": None}
    else:
        assert first_result["ok"] is False
        assert first_result["error"]["code"] == expected_code
    assert json.loads(messages[3]["content"])["data"] == 3
    assert requests[1].kwargs["tool_choice"] == "none"
    factory.return_value.__exit__.assert_called_once()


def test_direct_answer_does_not_send_second_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    client = MagicMock()
    client.chat.completions.create.return_value = completion({"role": "assistant", "content": "42"})
    with patch("agent_runtime.model_client.OpenAI") as factory:
        factory.return_value.__enter__.return_value = client
        main()

    client.chat.completions.create.assert_called_once()
