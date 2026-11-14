# agent-runtime

使用原生 tool calling 实现极简 Agent 运行时，不依赖 LangChain。模型负责提出工具调用，程序负责查找工具、校验参数、执行与回传结果，直到模型回答或触发终止条件。

## 当前能力

- 泛型 `Tool` 保存名称、描述、参数模型、执行函数、读写类型和超时时间。
- `ToolRegistry` 按名称注册与查找工具，拒绝重复名称，并导出工具参数 JSON Schema。
- Pydantic 校验输入；`ToolResult` / `ToolError` 统一表达执行结果。
- 执行器处理未知工具、非法参数、执行异常、人工拒绝和等待超时。
- `ToolEffect.READ` 工具直接执行；`WRITE` 工具在参数校验后通过终端确认，只有输入 `yes` 才执行（忽略首尾空白和大小写）。
- 后台线程执行工具，按工具配置限时等待，默认 10 秒；配置必须是有限正数。
- DeepSeek 客户端与调度循环分离，支持一轮多个工具调用和连续多轮调用。
- 保存用户消息、模型调用请求、工具结果和最终回答，通过 `tool_call_id` 对应请求与结果。
- 最多请求模型 5 轮；正常回答时结束，输出截断时停止。

当前具体工具只有整数加法 `add`。写工具确认由模拟工具测试覆盖，尚未提供真实写入业务工具。重试、幂等、强制取消和任务恢复尚未实现。

## 快速开始

环境：Python 3.15、uv；本机验证使用 Windows PowerShell 和 Python 3.15.2。依赖版本由 `uv.lock` 锁定。

在项目根目录安装依赖：

```powershell
uv sync --locked
```

若 uv 不在 PATH，但已安装到用户目录，可使用项目脚本：

```powershell
.\scripts\dev.ps1 setup
```

未安装 uv 时，参考 [uv 安装说明](https://docs.astral.sh/uv/getting-started/installation/)。

### 配置 DeepSeek

仅在 `.env` 不存在时复制模板，避免覆盖已有配置：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

在 `.env` 中填写：

```dotenv
DEEPSEEK_API_KEY=你的实际Key
DEEPSEEK_MODEL=deepseek-flash
```

`DEEPSEEK_API_KEY` 必填；未设置 `DEEPSEEK_MODEL` 时，代码默认使用 `deepseek-flash`。模型名称应与账号可用模型一致。接口地址目前在运行时演示入口中设为 `https://api.deepseek.com`，客户端关闭思考模式。

程序通过 `os.environ` 读取配置，由 uv 加载 `.env`，不直接读取该文件。已有同名环境变量优先于 `.env`；修改文件后若仍使用旧配置，请检查当前终端变量。`.env` 已被 Git 忽略。

### 运行真实模型演示

```powershell
uv run --env-file .env python -m agent_runtime.runtime
```

当前演示问题在 `runtime.py` 的直接运行入口中设为“1+123等于多少？”。它会请求真实模型，产生 API 用量。典型流程：

```text
第 1 轮：模型请求 add(a=1, b=123)
执行器：返回 {"ok": true, "data": 124, "error": null}
第 2 轮：模型根据工具结果回答
最终回答：1 + 123 = 124
```

模型选择的步骤和回答文字可能不同。`AgentRuntime.run(user_input)` 接收问题并返回字符串；正常回答返回内容，截断与轮数耗尽目前返回提示文字，尚未抽象为运行状态对象。模型请求异常仍向调用方传播。

注意入口区别：`uv run agent-runtime`、`python -m agent_runtime` 和 `scripts/dev.ps1 run` 目前仍是输出 `Hello from agent-runtime!` 的包骨架入口。真正的 Agent 演示使用上面的 `agent_runtime.runtime` 模块。`model_client.py` 现在只定义通信类，不再包含独立演示。

## 执行流程

```text
用户问题 + 工具说明
    ↓
请求模型（最多 5 轮）
    ├─ 输出截断 → 停止并返回提示
    ├─ 无工具调用 → 记录并返回回答
    └─ 有工具调用 → 记录模型请求
                      ↓
                 解析 JSON 参数
                      ↓
                 查找工具、校验参数
                      ↓
                 写工具请求人工确认
                      ↓
                 后台执行并限时等待
                      ↓
                 追加每个工具的结果 → 下一轮请求
```

工具执行失败也作为结果回传模型。人工确认不计入工具等待超时；确认输入关闭或被中断时，不执行工具，异常向外传播。

## 工具定义

工具专用参数模型和函数放在同一个文件，例如 `tools/add.py`。注册示例：

```python
from agent_runtime.registry import Tool, ToolEffect, ToolRegistry
from agent_runtime.tools.add import AddArgs, add

registry = ToolRegistry()
registry.register(
    Tool[AddArgs, int](
        name="add",
        description="两个整数相加",
        args_model=AddArgs,
        effect=ToolEffect.READ,
        handler=add,
        timeout_seconds=10.0,
    )
)
```

当前 `AgentRuntime.run()` 内部创建注册表并注册加法工具。新增工具需要在该处注册；外部注入注册表留待后续整理。读写标记由开发者指定，不接受模型自行指定执行权限。

`ToolExecutor.execute(name, args)` 返回 `ToolResult`：通过 `.ok`、`.data`、`.error` 访问字段，通过 `.model_dump()` 转为字典，或 `.model_dump_json()` 转为 JSON 字符串。

| 错误码 | 含义 |
| --- | --- |
| `TOOL_NOT_FOUND` | 工具不存在 |
| `INVALID_ARGUMENTS` | 参数校验失败；运行时也用它表达 JSON 解析失败或输入不是对象 |
| `USER_REJECTED` | 用户没有确认写操作，工具未执行 |
| `TOOL_EXECUTION_FAILED` | 工具执行抛出异常 |
| `TOOL_TIMEOUT` | 等待超过配置时限，工具可能仍在运行 |

## 超时与当前边界

- 模型请求在演示入口配置 `timeout=60.0`、`max_retries=0`；这与每个工具的等待超时是两套配置。
- 工具使用 `ThreadPoolExecutor` 执行。超时只停止等待，不能强制终止正在运行的线程。
- `shutdown(wait=False, cancel_futures=True)` 不等待活动任务，只取消尚未开始的任务；反复超时可能累积后台线程，进程退出仍可能等待线程完成。
- 写操作超时不代表外部操作失败，不能据此盲目重试。当前没有自动重试，Tenacity 虽已安装但尚未接入。
- 读写标记与确认不是沙箱或业务鉴权。工具自身仍需实现访问控制、输入约束等业务规则。
- `ToolResult.data` 仍是 `Any`，尚未统一限制可序列化的返回类型。
- 当前按 DeepSeek 接口实现；切换其他厂商不能保证只改 Key、模型和地址即可。尤其手动重建调用消息可能丢失 Gemini 等服务需要的附加字段，多厂商兼容尚未完成。

## 开发与测试

运行全部检查：

```powershell
.\scripts\dev.ps1 check
```

截至 2026-11-14，46 个本地测试通过，覆盖工具参数、注册与查找、执行结果、人工确认、线程等待超时、多轮历史、轮数限制、截断和客户端参数传递。测试使用模拟客户端，不读取真实 Key，也不发送模型请求。

| 命令 | 用途 |
| --- | --- |
| `uv run ruff check .` | 代码规范检查 |
| `uv run ruff check --select I --fix .` | 整理导入 |
| `uv run ruff format .` | 格式化代码 |
| `uv run mypy` | 严格类型检查 |
| `uv run pytest` | 全部测试 |
| `uv run pytest tests/test_executor.py -v` | 执行器测试 |
| `.\scripts\dev.ps1 build` | 构建 wheel 和源码分发包到 `dist/` |

脚本还提供 `setup`、`test`、`format`、`run` 任务，每次先执行 `uv sync --locked`，失败即停止。Cursor 项目设置位于 `.vscode/`，安装 Ruff 扩展后，显式保存 Python 文件可触发格式化、导入整理和安全自动修复。

新增依赖使用 `uv add <包名>`，开发依赖使用 `uv add --dev <包名>`，同时提交 `pyproject.toml` 和 `uv.lock`。

## 项目结构

```text
src/agent_runtime/
├── __init__.py       原有包骨架入口
├── __main__.py       python -m agent_runtime 入口
├── registry.py       Tool、ToolEffect、ToolRegistry 与 Schema 导出
├── executor.py       参数校验、人工确认、后台执行和等待超时
├── schemas.py        ToolResult、ToolError
├── model_client.py   DeepSeek 请求适配
├── runtime.py        多轮循环及直接运行演示
└── tools/add.py      AddArgs 参数模型与 add 函数

tests/
├── test_smoke.py         包启动测试
├── test_registry.py      注册表与超时配置测试
├── test_executor.py      执行器、确认与超时测试
├── test_model_client.py  模型请求适配测试
├── test_runtime.py       模拟模型的多轮循环测试
└── tools/test_add.py     加法与参数校验测试

scripts/dev.ps1       Windows 开发任务入口
docs/daily/           开发日报
.env.example          配置模板，不含真实 Key
pyproject.toml        项目、依赖和检查配置
uv.lock               依赖锁文件
```

## 后续计划

1. 增加适用于读取操作的有限重试，区分错误类别；写操作引入幂等与状态确认。
2. 完善任务执行隔离与资源限制，明确取消语义。
3. 将人工确认抽成可替换接口，支持终端之外的调用方。
4. 引入明确的运行状态结果，支持注册表注入和统一配置。
5. 增加真实业务工具、结构化日志、耗时与 token 统计、固定任务评估。
6. 完善多厂商消息适配、接口异常和任务恢复策略。

初始环境建设记录见 [2026-11-12 日报](docs/daily/2026-11-12.md)；该日报是当天快照，当前能力以本 README 和代码为准。
