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
