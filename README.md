# agent-runtime

用原生 tool calling 实现一个极简、可扩展的 Agent 调度器，重点展示运行时基础能力，而非仅封装框架。

目标流程：模型输出结构化 action → 路由到工具注册表 → 校验并执行工具 → 捕获异常、返回 observation → 放回上下文继续循环。

计划支持注册式工具、参数 Schema 校验、超时、重试、读写副作用区分，以及人工确认点（human-in-the-loop）。

## 当前状态

已完成 Python 包骨架、依赖锁定、开发检查、启动冒烟测试和打包验证。入口目前输出 `Hello from agent-runtime!`；模型调用、工具注册表和调度循环尚未实现。

## 开发环境

- Python 3.15（沿用 `.python-version`；本机验证版本为 3.15.2）。
- uv 管理虚拟环境、依赖与构建；`uv.lock` 应提交到版本控制。
- 运行依赖：OpenAI SDK、Pydantic、Tenacity。
- 开发依赖：Ruff（代码检查与格式化）、mypy（严格类型检查）、pytest（测试）。

Windows PowerShell 中，在项目目录运行：

```powershell
.\scripts\dev.ps1 setup
.\scripts\dev.ps1 check
.\scripts\dev.ps1 run
```

脚本优先使用 PATH 中的 uv，也支持本机安装位置 `$env:USERPROFILE\.local\bin\uv.exe`，无需激活虚拟环境。每次运行先执行 `uv sync --locked`，保证配置与锁文件一致；任一步失败会停止。首次同步需要下载依赖。

若未安装 uv，可按 [uv 安装文档](https://docs.astral.sh/uv/getting-started/installation/) 安装后重新打开终端。若 PowerShell 提示脚本执行策略限制，可使用下方的 uv 命令，不必更改系统策略。

其他系统或已配置 uv 的终端可直接运行：

```sh
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked pytest
uv run --locked agent-runtime
uv run --locked python -m agent_runtime
```

## 常用任务

| PowerShell 命令 | 用途 |
| --- | --- |
| `.\scripts\dev.ps1 setup` | 按锁文件安装运行和开发依赖 |
| `.\scripts\dev.ps1 check` | 检查代码、格式、类型并运行测试 |
| `.\scripts\dev.ps1 test` | 运行测试 |
| `.\scripts\dev.ps1 format` | 格式化代码 |
| `.\scripts\dev.ps1 run` | 启动当前入口 |
| `.\scripts\dev.ps1 build` | 生成 wheel 和源码分发包到 `dist/` |

新增运行依赖用 `uv add <包名>`，开发依赖用 `uv add --dev <包名>`；同时提交 `pyproject.toml` 与 `uv.lock`。不要手工修改锁文件。

## 配置与目录

`.env.example` 预留模型接入所需变量，可复制为 `.env`。当前入口不读取 `.env`，也不调用模型；启动和测试均不需要 API Key。接入模型时需显式实现配置读取。`.env`、虚拟环境、缓存和构建产物已加入 Git 忽略规则。

```text
src/agent_runtime/   Python 包与启动入口
tests/              无网络启动冒烟测试
scripts/dev.ps1     Windows 开发任务入口
docs/daily/         按日期记录的开发日报
pyproject.toml      项目、依赖和检查配置
uv.lock             可复现依赖版本
```

## 后续开发顺序

### 代码层级约定

采用按职责划分的小型结构；下列标注“计划”的文件在实现相应能力时再创建。

```text
src/agent_runtime/
├── __init__.py          包初始化与现有 main 入口
├── __main__.py          python -m agent_runtime 启动入口
├── tools/
│   ├── __init__.py      工具子包初始化
│   └── add.py           AddArgs 参数模型；后续添加 add 工具函数
├── schemas.py          [计划] 通用 Action / Observation 数据模型
├── registry.py         [计划] 工具定义与注册、按名称查找
├── executor.py         [计划] 校验、执行、异常处理、超时与重试
├── runtime.py          [计划] 调度循环、上下文管理与终止条件
└── model_client.py     [计划] 模型 SDK 接入与消息格式转换

tests/
├── test_smoke.py        启动冒烟测试
├── tools/
│   └── test_add.py      [计划] 加法工具与参数校验测试
├── test_registry.py    [计划] 注册表测试
├── test_executor.py    [计划] 执行器测试
└── test_runtime.py     [计划] 使用模拟模型的循环测试
```

约定：

- 工具专用参数模型与工具函数放在同一文件，例如 `tools/add.py`；只有跨工具共用的协议才放入 `schemas.py`。
- Python 文件名使用小写下划线，类名使用大驼峰；不要求一个类对应一个文件。
- 工具模块不负责调用模型；执行器不决定对话下一步；调度循环通过执行器调用工具。
- `__init__.py` 保持简单，不堆放业务代码；现有启动函数后续扩展时再迁出。
- 测试集中放在项目根目录的 `tests/` 中，目录尽量对应源码职责。

### 实现顺序

1. 定义 action / observation 数据模型和基于 Pydantic 的工具注册表。
2. 实现工具执行器：参数校验、异常结构化、超时与重试；写工具避免默认重试。
3. 实现模型适配与调度循环，增加最大轮数和终止条件。
4. 增加读写工具权限与人工确认点，覆盖拒绝、失败和超时路径。
5. 增加无网络模拟模型测试，再进行真实模型联调。

开发记录见 [2026-11-12 日报](docs/daily/2026-11-12.md)。
