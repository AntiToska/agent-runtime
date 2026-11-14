import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from openai.types.chat import ChatCompletion

from agent_runtime.model_client import DeepSeekClient
from agent_runtime.runtime import AgentRuntime


def completion(message: dict[str, Any], finish_reason: str | None = None) -> ChatCompletion:
    if finish_reason is None:
        finish_reason = "tool_calls" if message.get("tool_calls") else "stop"
    return ChatCompletion.model_validate(
        {
            "id": "test-response",
            "object": "chat.completion",
            "created": 0,
            "model": "test-model",
            "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
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
    runtime = AgentRuntime(DeepSeekClient(client, "test-model"))
    result = runtime.run("测试用户输入")

    requests = client.chat.completions.create.call_args_list
    assert result == "Done"
    assert len(requests) == 2
    assert requests[0].kwargs["messages"] == [{"role": "user", "content": "测试用户输入"}]
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
    assert all(request.kwargs["tool_choice"] == "auto" for request in requests)


def test_direct_answer_does_not_send_second_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    client = MagicMock()
    client.chat.completions.create.return_value = completion({"role": "assistant", "content": "42"})
    runtime = AgentRuntime(DeepSeekClient(client, "test-model"))
    result = runtime.run("测试用户输入")

    assert result == "42"
    client.chat.completions.create.assert_called_once()


def tool_response(call_id: str, a: int, b: int) -> ChatCompletion:
    return completion(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": "add", "arguments": json.dumps({"a": a, "b": b})},
                }
            ],
        }
    )


def test_multiple_tool_rounds_preserve_history(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        tool_response("round-1", 12, 30),
        tool_response("round-2", 42, 8),
        completion({"role": "assistant", "content": "最终结果是 50"}),
    ]
    runtime = AgentRuntime(DeepSeekClient(client, "test-model"))
    result = runtime.run("测试用户输入")

    requests = client.chat.completions.create.call_args_list
    assert result == "最终结果是 50"
    assert len(requests) == 3
    assert [len(request.kwargs["messages"]) for request in requests] == [1, 3, 5]
    messages = requests[2].kwargs["messages"]
    assert [message["role"] for message in messages] == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
    ]
    for index, call_id, total in [(2, "round-1", 42), (4, "round-2", 50)]:
        assert messages[index - 1]["tool_calls"][0]["id"] == call_id
        assert messages[index]["tool_call_id"] == call_id
        assert json.loads(messages[index]["content"])["data"] == total
    output = capsys.readouterr().out
    assert "最终结果是 50" in output
    assert "已达到最大请求轮数" not in output


def test_empty_answer_still_returns_string() -> None:
    client = MagicMock()
    client.chat.completions.create.return_value = completion({"role": "assistant", "content": None})

    assert AgentRuntime(DeepSeekClient(client, "test-model")).run("hello") == ""


def test_separate_runs_do_not_reuse_message_history() -> None:
    client = MagicMock()
    client.chat.completions.create.return_value = completion(
        {"role": "assistant", "content": "answer"}
    )
    runtime = AgentRuntime(DeepSeekClient(client, "test-model"))

    assert runtime.run("first question") == "answer"
    assert runtime.run("second question") == "answer"

    requests = client.chat.completions.create.call_args_list
    assert requests[0].kwargs["messages"] == [{"role": "user", "content": "first question"}]
    assert requests[1].kwargs["messages"] == [{"role": "user", "content": "second question"}]


def test_repeated_tool_calls_stop_at_round_limit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        tool_response(f"round-{index}", index, 1) for index in range(6)
    ]
    runtime = AgentRuntime(DeepSeekClient(client, "test-model"))
    result = runtime.run("测试用户输入")

    assert result == "已达到最大请求轮数，任务尚未确认完成"
    assert client.chat.completions.create.call_count == 5
    output = capsys.readouterr().out
    assert "已达到最大请求轮数，任务尚未确认完成" in output
    assert "模型没有请求工具调用，回答" not in output


@pytest.mark.parametrize("with_tool_call", [False, True])
def test_truncated_response_stops_without_executing_tools(
    with_tool_call: bool,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    response = (
        tool_response("truncated-call", 12, 30)
        if with_tool_call
        else completion({"role": "assistant", "content": "不完整回答"})
    )
    response.choices[0].finish_reason = "length"
    client = MagicMock()
    client.chat.completions.create.return_value = response
    with (
        patch("agent_runtime.runtime.ToolExecutor.execute") as execute,
    ):
        runtime = AgentRuntime(DeepSeekClient(client, "test-model"))
        result = runtime.run("测试用户输入")

    assert result == "模型输出达到长度限制，本轮未完成"
    execute.assert_not_called()
    client.chat.completions.create.assert_called_once()
    output = capsys.readouterr().out
    assert "模型输出达到长度限制，本轮未完成" in output
    assert "模型没有请求工具调用，回答" not in output
    assert "已达到最大请求轮数" not in output
