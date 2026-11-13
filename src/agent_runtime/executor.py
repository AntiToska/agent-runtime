from typing import Any

from pydantic import ValidationError

from agent_runtime.registry import Tool, ToolRegistry
from agent_runtime.tools.add import AddArgs, add


class ToolExecutor:
    def __init__(self, tool_registry: ToolRegistry) -> None:
        self.tool_registry = tool_registry

    def execute(
        self,
        name: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            tool = self.tool_registry.get(name)
        except ValueError as error:
            return {
                "ok": False,
                "error": {
                    "code": "TOOL_NOT_FOUND",
                    "message": str(error),
                },
            }
        try:
            validated_args = tool.args_model.model_validate(args)
        except ValidationError as error:
            return {
                "ok": False,
                "error": {
                    "code": "INVALID_ARGUMENTS",
                    "message": str(error),
                },
            }
        try:
            result = tool.handler(validated_args)
        except Exception as error:
            return {
                "ok": False,
                "error": {
                    "code": "TOOL_EXECUTION_FAILED",
                    "message": str(error),
                },
            }
        return {"ok": True, "data": result}


if __name__ == "__main__":
    registry = ToolRegistry()
    registry.register(
        Tool[AddArgs, int](
            name="add",
            description="两个整数相加",
            args_model=AddArgs,
            handler=add,
        )
    )

    executor = ToolExecutor(registry)

    result = executor.execute("add", {"a": 1, "b": 2})
    print(result)
# {"ok": True, "data": 3}
