## Why

当前系统已经能完成黄金研究流程，但运行时仍要求用户提供自定义 agent API 地址和实时金价 URL，这与“直接兼容 OpenAI 风格配置”和“由系统自行完成实时查价”这两个实际使用需求不匹配。现在补上这层兼容和自动化边界，可以让后端更容易启动，也能让研究 workflow 更接近真实使用方式。

## What Changes

- 将多 Agent 分析从自定义 `/agents/{name}` HTTP 协议扩展为直接兼容 OpenAI-compatible API。
- 增加 `DATABASE_URL`、`OPENAI_API_KEY`、`GOLDFXGRAPH_OPENAI_MODEL`、`GOLDFXGRAPH_OPENAI_BASE_URL` 配置兼容。
- 调整本地开发配置文件约定，使项目可以直接以这组 OpenAI 风格变量启动，但 committed 配置文件仅保留 placeholder，不提交真实 secret。
- 将实时金价获取改为后端内置的自动 quote discovery tool，不再要求用户手填 quote URL。
- 保持 FastAPI、LangGraph、结构化 forecast 输出和 PostgreSQL 持久化边界不变。

## Capabilities

### New Capabilities
- `openai-compatible-agent-client`: 为 LangGraph agent 节点提供 OpenAI-compatible 模型调用与结构化结果解析能力

### Modified Capabilities
- `backend-research-api`: 后端配置与 API 运行前提改为兼容 OpenAI 风格配置，并允许在无手工 quote URL 情况下运行研究流程
- `market-data-and-indicators`: current quote 获取策略改为系统自动发现并查询候选数据源，而非仅依赖显式配置 URL
- `langgraph-forecast-workflow`: agent 节点调用方式改为优先使用 OpenAI-compatible 模型，并在失败时回退 deterministic 输出

## Impact

- 影响 `src/goldfxgraph/packages/common/settings.py`
- 影响 `src/goldfxgraph/market_data/current_quote.py`
- 影响 `src/goldfxgraph/workflow/nodes.py`
- 新增 OpenAI-compatible client 模块与测试
- 更新 API / workflow / market data / settings 相关测试
