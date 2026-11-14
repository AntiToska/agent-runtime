from typing import Any

from pydantic import ValidationError

from agent_runtime.registry import Tool, ToolEffect, ToolRegistry
from agent_runtime.schemas import ToolError, ToolResult
from agent_runtime.tools.add import AddArgs, add


class ToolExecutor:
    def __init__(self, tool_registry: ToolRegistry) -> None:
        self.tool_registry = tool_registry

    def execute(
        self,
        name: str,
        args: dict[str, Any],
    ) -> ToolResult:
        try:
            tool = self.tool_registry.get(name)
        except ValueError as error:
            return ToolResult(
                ok=False,
                error=ToolError(code="TOOL_NOT_FOUND", message=str(error)),
            )
        try:
            validated_args = tool.args_model.model_validate(args)
        except ValidationError as error:
            return ToolResult(
                ok=False,
                error=ToolError(code="INVALID_ARGUMENTS", message=str(error)),
            )
        if tool.effect == ToolEffect.WRITE:
            print(f"准备执行写操作：{tool.name}")
            print("参数：", validated_args.model_dump())
            confirmation = input("确认执行？输入 yes 继续：").strip().lower()
            if confirmation != "yes":
                return ToolResult(
                    ok=False,
                    error=ToolError(
                        code="USER_REJECTED",
                        message="用户未确认，操作未执行",
                    ),
                )
        try:
            result = tool.handler(validated_args)
        except Exception as error:
            return ToolResult(
                ok=False,
                error=ToolError(code="TOOL_EXECUTION_FAILED", message=str(error)),
            )
        return ToolResult(ok=True, data=result)


if __name__ == "__main__":
    registry = ToolRegistry()
    registry.register(
        Tool[AddArgs, int](
            name="add",
            description="两个整数相加",
            args_model=AddArgs,
            effect=ToolEffect.READ,
            handler=add,
        )
    )

    executor = ToolExecutor(registry)

    result = executor.execute("add", {"a": 1, "b": 2})
    print(result.model_dump())
    # {"ok": True, "data": 3, "error": None}
