import math
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ToolEffect(StrEnum):
    READ = "read"
    WRITE = "write"


# 保存工具配置的对象：名称、说明、参数类、执行函数。
class Tool[ArgsT: BaseModel, ResultT]:
    def __init__(
        self,
        name: str,
        description: str,
        args_model: type[ArgsT],
        effect: ToolEffect,
        handler: Callable[[ArgsT], ResultT],
        timeout_seconds: float = 10.0,
    ) -> None:
        self.name = name
        self.description = description
        self.args_model = args_model
        self.effect = effect
        self.handler = handler
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须是有限的正数")
        self.timeout_seconds = timeout_seconds


# 工具注册类，初始化、新增、获取工具、获取工具说明
class ToolRegistry:
    def __init__(self) -> None:
        self.tools: dict[str, Tool[Any, Any]] = {}

    def register(self, tool: Tool[Any, Any]) -> None:
        if tool.name in self.tools:
            raise ValueError(f"Tool {tool.name} already registered")
        self.tools[tool.name] = tool

    def get(self, name: str) -> Tool[Any, Any]:
        if name not in self.tools:
            raise ValueError(f"Tool {name} not found")
        return self.tools[name]

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        schemas = []
        for tool in self.tools.values():
            schemas.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.args_model.model_json_schema(),
                }
            )
        return schemas
