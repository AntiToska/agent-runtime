import pytest

from agent_runtime.executor import ToolExecutor
from agent_runtime.registry import Tool, ToolRegistry
from agent_runtime.schemas import ToolResult
from agent_runtime.tools.add import AddArgs, add


def test_execute_returns_success_model() -> None:
    registry = ToolRegistry()
    registry.register(Tool("add", "Add integers", AddArgs, add))

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
    registry.register(Tool("add", "Add integers", AddArgs, handler))

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
    registry.register(Tool("fail", "Fail deliberately", AddArgs, handler))

    result = ToolExecutor(registry).execute("fail", {"a": 1, "b": 2})

    assert result.ok is False
    assert result.data is None
    assert result.error is not None
    assert result.error.code == "TOOL_EXECUTION_FAILED"
    assert result.error.message == "tool failed"
