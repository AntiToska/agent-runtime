import json
import os

from openai import OpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.chat.chat_completion_tool_param import ChatCompletionToolParam

from agent_runtime.executor import ToolExecutor
from agent_runtime.model_client import DeepSeekClient
from agent_runtime.registry import Tool, ToolRegistry
from agent_runtime.schemas import ToolError, ToolResult
from agent_runtime.tools.add import AddArgs, add


class AgentRuntime:
    def __init__(self, model_client: DeepSeekClient) -> None:
        self.model_client = model_client

    def run(self, user_input: str) -> str:
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

        # 保存用户问题，后续持续追加消息，而不是只发送孤立的工具结果。
        messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": user_input}]
        executor = ToolExecutor(registry)
        max_rounds = 5
        for round_index in range(max_rounds):
            print(f"第 {round_index + 1} 轮")
            response = self.model_client.chat(messages.copy(), tools)
            choice = response.choices[0]
            message = choice.message
            if choice.finish_reason == "length":
                print("模型输出达到长度限制，本轮未完成")
                return "模型输出达到长度限制，本轮未完成"
            if not message.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.content,
                    }
                )
                print("模型没有请求工具调用，回答：", message.content)
                print("messages:", messages)
                return message.content or ""

            # 当前只向模型提供 function 工具。
            function_calls = [call for call in message.tool_calls if call.type == "function"]
            if len(function_calls) != len(message.tool_calls):
                raise ValueError("模型返回了不支持的工具调用类型")

            # 先记录模型的完整调用请求，再逐个追加对应结果。
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
        else:
            print("已达到最大请求轮数，任务尚未确认完成")
            return "已达到最大请求轮数，任务尚未确认完成"


if __name__ == "__main__":
    with OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
        timeout=60.0,
        max_retries=0,
    ) as sdk_client:
        model_client = DeepSeekClient(
            client=sdk_client,
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
        )
        deepSeek_agent = AgentRuntime(model_client)
        result = deepSeek_agent.run("1+123等于多少？")
        print("最终回答：" + result)
