import json
import os

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

from agent_runtime.executor import ToolExecutor
from agent_runtime.registry import Tool, ToolRegistry
from agent_runtime.schemas import ToolError, ToolResult
from agent_runtime.tools.add import AddArgs, add


def main() -> None:
    registry = ToolRegistry()
    registry.register(
        Tool[AddArgs, int](
            name="add",
            description="两个整数相加",
            args_model=AddArgs,
            handler=add,
        )
    )
    # 给每个工具说明套一层 Chat Completions 接口要求的格式。
    tools: list[ChatCompletionToolParam] = [
        {
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema["description"],
                "parameters": schema["parameters"],
            },
        }
        for schema in registry.get_tool_schemas()
    ]

    # 1. 保存用户问题，后续持续追加消息，而不是只发送孤立的工具结果。
    messages: list[ChatCompletionMessageParam] = [
        {"role": "user", "content": "请使用 add 工具计算 12 + 30。"}
    ]
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
    executor = ToolExecutor(registry)

    with OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
        timeout=60.0,
        max_retries=0,
    ) as client:
        response = client.chat.completions.create(
            model=model,
            messages=messages.copy(),
            tools=tools,
            extra_body={"thinking": {"type": "disabled"}},
        )

        message = response.choices[0].message
        if not message.tool_calls:
            print("模型没有请求工具调用，回答：", message.content)
            return

        # 当前只向模型提供 function 工具。
        function_calls = [call for call in message.tool_calls if call.type == "function"]
        if len(function_calls) != len(message.tool_calls):
            raise ValueError("模型返回了不支持的工具调用类型")

        # 2. 先记录模型的完整调用请求，再逐个追加对应结果。
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in function_calls
                ],
            }
        )

        for tool_call in function_calls:
            print("调用 ID：", tool_call.id)
            print("工具名：", tool_call.function.name)
            print("参数（JSON 字符串）：", tool_call.function.arguments)
            # 模型返回的 arguments 是 JSON 字符串，先转成字典
            try:
                arguments = json.loads(tool_call.function.arguments)
                if not isinstance(arguments, dict):
                    raise ValueError("工具参数必须是 JSON 对象")
            except ValueError as error:
                result = ToolResult(
                    ok=False,
                    error=ToolError(code="INVALID_ARGUMENTS", message=str(error)),
                )
            else:
                result = executor.execute(tool_call.function.name, arguments)
            print("工具执行结果：", result.model_dump())

            # 3. tool_call_id 将执行结果与前面的调用请求一一对应。
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result.model_dump_json(),
                }
            )

        # 4. 本阶段只演示两次请求；第二次要求模型根据结果直接回答。
        final_response = client.chat.completions.create(
            model=model,
            messages=messages.copy(),
            tools=tools,
            tool_choice="none",
            extra_body={"thinking": {"type": "disabled"}},
        )
        print("模型最终回答：", final_response.choices[0].message.content)


if __name__ == "__main__":
    main()
