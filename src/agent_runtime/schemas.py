"""Shared result models for tool execution."""

from typing import Any, Literal

from pydantic import BaseModel


class ToolError(BaseModel):
    code: Literal[
        "TOOL_NOT_FOUND",
        "INVALID_ARGUMENTS",
        "TOOL_EXECUTION_FAILED",
        "USER_REJECTED",
        "TOOL_TIMEOUT",
    ]
    message: str


class ToolResult(BaseModel):
    ok: bool
    data: Any = None
    error: ToolError | None = None
