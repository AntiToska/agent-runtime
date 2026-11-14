import pytest

from agent_runtime.registry import Tool, ToolEffect, ToolRegistry
from agent_runtime.tools.add import AddArgs, add


def test_get_returns_registered_tool() -> None:
    registry = ToolRegistry()
    tool = Tool[AddArgs, int](
        name="add",
        description="Add two integers",
        args_model=AddArgs,
        effect=ToolEffect.READ,
        handler=add,
    )

    registry.register(tool)

    assert registry.get("add") is tool


def test_duplicate_registration_preserves_original() -> None:
    registry = ToolRegistry()
    original = Tool[AddArgs, int](
        name="add",
        description="Original tool",
        args_model=AddArgs,
        effect=ToolEffect.READ,
        handler=add,
    )
    replacement = Tool[AddArgs, int](
        name="add",
        description="Replacement tool",
        args_model=AddArgs,
        effect=ToolEffect.READ,
        handler=add,
    )
    registry.register(original)

    with pytest.raises(ValueError, match="Tool add already registered"):
        registry.register(replacement)

    assert registry.get("add") is original


def test_get_unknown_tool_raises_error() -> None:
    registry = ToolRegistry()

    with pytest.raises(ValueError, match="Tool missing not found"):
        registry.get("missing")


@pytest.mark.parametrize("timeout", [0.0, -1.0, float("nan"), float("inf"), float("-inf")])
def test_tool_rejects_invalid_timeout(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        Tool("add", "Add", AddArgs, ToolEffect.READ, add, timeout_seconds=timeout)


def test_tool_timeout_default_and_override() -> None:
    assert Tool("add", "Add", AddArgs, ToolEffect.READ, add).timeout_seconds == 10.0
    tool = Tool("add", "Add", AddArgs, ToolEffect.READ, add, timeout_seconds=0.25)
    assert tool.timeout_seconds == 0.25
