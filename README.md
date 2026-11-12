# agent-runtime
原生手撸一轮 tool calling，不要只套 LangChain 写一个极简调度器：模型输出结构化 action → 路由到工具注册表 → 执行、捕获异常、返回 observation → 放回上下文继续循环；重点体现：不是 if-else，是注册式、可扩展工具，参数 Schema 校验、超时、重试、区分读 / 写（副作用）、人工确认点（human-in-the-loop）。 这是这家公司最看重的：他们是做基座，不是套壳。 如何开始
