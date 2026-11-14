from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock, patch

import pytest

from agent_runtime.executor import ToolExecutor
from agent_runtime.registry import Tool, ToolEffect, ToolRegistry
from agent_runtime.schemas import ToolResult
from agent_runtime.tools.add import AddArgs, add


def test_execute_returns_success_model() -> None:
    registry = ToolRegistry()
    registry.register(Tool("add", "Add integers", AddArgs, ToolEffect.READ, add))

    result = ToolExecutor(registry).execute("add", {"a": 1, "b": 2})

    assert isinstance(result, ToolResult)
    assert result.ok is True
    assert result.data == 3
    assert result.error is None
    assert result.model_dump() == {"ok": True, "data": 3, "error": None}


def test_execute_unknown_tool_returns_error_model() -> None:
    result = ToolExecutor(ToolRegistry()).execute("missing", {})

    assert result.ok is False
    assert result.data is None
    assert result.error is not None
    assert result.error.code == "TOOL_NOT_FOUND"
    assert "missing" in result.error.message


@pytest.mark.parametrize("arguments", [{"a": "1", "b": 2}, {"a": 1}])
def test_invalid_arguments_do_not_call_handler(arguments: dict[str, object]) -> None:
    calls: list[AddArgs] = []

    def handler(args: AddArgs) -> int:
        calls.append(args)
        return add(args)

    registry = ToolRegistry()
    registry.register(Tool("add", "Add integers", AddArgs, ToolEffect.READ, handler))

    result = ToolExecutor(registry).execute("add", arguments)

    assert result.ok is False
    assert result.data is None
    assert result.error is not None
    assert result.error.code == "INVALID_ARGUMENTS"
    assert result.error.message
    assert calls == []


@pytest.mark.parametrize("exception_type", [RuntimeError, ValueError])
def test_handler_exception_is_execution_failure(exception_type: type[Exception]) -> None:
    def handler(args: AddArgs) -> int:
        raise exception_type("tool failed")

    registry = ToolRegistry()
    registry.register(Tool("fail", "Fail deliberately", AddArgs, ToolEffect.READ, handler))

    result = ToolExecutor(registry).execute("fail", {"a": 1, "b": 2})

    assert result.ok is False
    assert result.data is None
    assert result.error is not None
    assert result.error.code == "TOOL_EXECUTION_FAILED"
    assert result.error.message == "tool failed"


def test_timeout_returns_before_background_tool_finishes() -> None:
    started = Event()
    release = Event()
    finished = Event()

    def handler(args: AddArgs) -> int:
        started.set()
        try:
            if not release.wait(timeout=5):
                raise RuntimeError("test did not release worker")
            return add(args)
        finally:
            finished.set()

    registry = ToolRegistry()
    registry.register(
        Tool(
            "slow", "Controlled slow tool", AddArgs, ToolEffect.READ, handler, timeout_seconds=0.05
        )
    )
    with ThreadPoolExecutor(max_workers=1) as caller:
        try:
            pending = caller.submit(ToolExecutor(registry).execute, "slow", {"a": 1, "b": 2})
            assert started.wait(timeout=2)
            result = pending.result(timeout=2)
            assert result.ok is False
            assert result.error is not None
            assert result.error.code == "TOOL_TIMEOUT"
            assert not finished.is_set()
        finally:
            release.set()
        assert finished.wait(timeout=2)


def test_handler_timeout_error_is_not_executor_wait_timeout() -> None:
    def handler(args: AddArgs) -> int:
        raise TimeoutError("upstream request timed out")

    registry = ToolRegistry()
    registry.register(Tool("fail", "Fail immediately", AddArgs, ToolEffect.READ, handler))

    result = ToolExecutor(registry).execute("fail", {"a": 1, "b": 2})

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "TOOL_EXECUTION_FAILED"
    assert result.error.message == "upstream request timed out"


def test_rejected_write_does_not_create_thread_pool() -> None:
    registry = ToolRegistry()
    registry.register(Tool("write", "Write demo", AddArgs, ToolEffect.WRITE, add))

    with (
        patch("builtins.input", return_value="no"),
        patch("agent_runtime.executor.ThreadPoolExecutor") as pool,
    ):
        result = ToolExecutor(registry).execute("write", {"a": 1, "b": 2})

    pool.assert_not_called()
    assert result.error is not None
    assert result.error.code == "USER_REJECTED"


def test_read_tool_does_not_request_confirmation() -> None:
    registry = ToolRegistry()
    registry.register(Tool("add", "Add integers", AddArgs, ToolEffect.READ, add))

    with patch("builtins.input") as confirm:
        result = ToolExecutor(registry).execute("add", {"a": 1, "b": 2})

    confirm.assert_not_called()
    assert result.ok is True
    assert result.data == 3


@pytest.mark.parametrize("answer", ["yes", " YES "])
def test_write_tool_executes_once_after_confirmation(answer: str) -> None:
    handler = Mock(return_value=3)
    registry = ToolRegistry()
    registry.register(Tool("write", "Write demo", AddArgs, ToolEffect.WRITE, handler))

    def confirm(prompt: str) -> str:
        handler.assert_not_called()
        return answer

    with patch("builtins.input", side_effect=confirm) as ask:
        result = ToolExecutor(registry).execute("write", {"a": 1, "b": 2})

    ask.assert_called_once()
    handler.assert_called_once_with(AddArgs(a=1, b=2))
    assert result.ok is True
    assert result.data == 3


@pytest.mark.parametrize("answer", ["no", "", "y", "anything"])
def test_write_tool_rejection_has_no_side_effect(answer: str) -> None:
    handler = Mock(return_value=3)
    registry = ToolRegistry()
    registry.register(Tool("write", "Write demo", AddArgs, ToolEffect.WRITE, handler))

    with patch("builtins.input", return_value=answer) as confirm:
        result = ToolExecutor(registry).execute("write", {"a": 1, "b": 2})

    confirm.assert_called_once()
    handler.assert_not_called()
    assert result.ok is False
    assert result.data is None
    assert result.error is not None
    assert result.error.code == "USER_REJECTED"


def test_invalid_write_arguments_do_not_prompt_or_execute() -> None:
    handler = Mock()
    registry = ToolRegistry()
    registry.register(Tool("write", "Write demo", AddArgs, ToolEffect.WRITE, handler))

    with patch("builtins.input") as confirm:
        result = ToolExecutor(registry).execute("write", {"a": "1", "b": 2})

    confirm.assert_not_called()
    handler.assert_not_called()
    assert result.error is not None
    assert result.error.code == "INVALID_ARGUMENTS"


@pytest.mark.parametrize("error_type", [EOFError, KeyboardInterrupt])
def test_confirmation_interruption_does_not_execute(error_type: type[BaseException]) -> None:
    handler = Mock()
    registry = ToolRegistry()
    registry.register(Tool("write", "Write demo", AddArgs, ToolEffect.WRITE, handler))

    with patch("builtins.input", side_effect=error_type), pytest.raises(error_type):
        ToolExecutor(registry).execute("write", {"a": 1, "b": 2})

    handler.assert_not_called()


def test_confirmed_write_failure_returns_execution_error() -> None:
    handler = Mock(side_effect=RuntimeError("write failed"))
    registry = ToolRegistry()
    registry.register(Tool("write", "Write demo", AddArgs, ToolEffect.WRITE, handler))

    with patch("builtins.input", return_value="yes"):
        result = ToolExecutor(registry).execute("write", {"a": 1, "b": 2})

    handler.assert_called_once()
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "TOOL_EXECUTION_FAILED"
