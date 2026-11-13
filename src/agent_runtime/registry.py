from collections.abc import Callable
from typing import Any

from pydantic import BaseModel


# 保存工具配置的对象：名称、说明、参数类、执行函数。
class Tool[ArgsT: BaseModel, ResultT]:
    def __init__(
        self,
        name: str,
        description: str,
        args_model: type[ArgsT],
        handler: Callable[[ArgsT], ResultT],
    ) -> None:
        self.name = name
        self.description = description
        self.args_model = args_model
        self.handler = handler


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
