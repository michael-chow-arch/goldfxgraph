## Why

GoldFXGraph 目前只有早期项目说明、依赖声明、PostgreSQL compose 和一份 XAUUSD 日线 CSV，还没有可运行的研究 API、结构化预测流程、持久化边界或前端 Dashboard。现在需要建立第一版端到端能力，让用户可以基于真实黄金数据触发研究流程，并在 Vue 3 页面中查看结构化预测结果。

## What Changes

- 新增 FastAPI 后端应用骨架，提供获取最新预测结果、创建研究运行、查询研究运行结果的第一版 API。
- 新增 `dev.env` 与 `.env.example` 配置约定，支持配置环境、日志级别、PostgreSQL URL、XAUUSD CSV 路径、当前金价数据源、agent API 地址和 agent API key。
- 从用户提供的 XAUUSD 日线 CSV 读取真实数据，验证必要字段，排序并选择最新完成日线 bar；需要当前/latest 金价时，通过可配置数据源获取并记录来源和时间。
- 计算第一版基础技术指标，用确定性工具节点为 LangGraph 工作流提供输入。
- 新增显式 LangGraph 多 Agent 研究 workflow，区分 router/tool/agent 节点，输出 Pydantic 结构化预测结果。
- 使用 SQLAlchemy + PostgreSQL 持久化研究运行记录和预测结果。
- 新增 Vue 3 + TypeScript + Vite + Tailwind CSS 前端项目，目录为 `apps/web/`，通过 typed service 调用 FastAPI，不在页面硬编码预测假数据。
- 新增黄金预测 Dashboard，清晰展示当前价格、方向判断、买入/止盈/止损、持有建议、多 Agent 摘要、风险提示和研究免责声明。
- 不实现自动交易、真实下单、券商接入、n8n、MCP、多模型路由、scorecard、完整评估系统或复杂 observability。

## Capabilities

### New Capabilities

- `backend-research-api`: 定义 FastAPI 第一版研究 API、配置加载、结构化响应和错误语义。
- `market-data-and-indicators`: 定义 XAUUSD CSV 数据读取、当前/latest 金价获取、数据来源记录和基础技术指标计算。
- `langgraph-forecast-workflow`: 定义 LangGraph 多 Agent 研究流程、节点职责和结构化预测输出。
- `forecast-persistence`: 定义 PostgreSQL 研究运行记录和预测结果持久化要求。
- `gold-forecast-dashboard`: 定义 Vue 3 + Tailwind 黄金预测 Dashboard 的数据获取、展示字段和页面状态。

### Modified Capabilities

- 无。当前仓库尚无已生效的 OpenSpec capability。

## Impact

- 后端代码新增于 `src/goldfxgraph/`，包括 settings、API、schemas、market data、indicators、workflow、persistence 等模块。
- 后端测试新增于 `tests/`，覆盖 CSV 校验、指标计算、结构化预测 schema、API 基础行为和持久化边界。
- 前端代码新增于 `apps/web/`，包括 Vite、Vue 3、Tailwind、typed API service、types、constants 和 Dashboard 页面。
- 配置文件影响 `.env.example`、新增 `dev.env`，并可能扩展 `pyproject.toml` 的后端依赖和新增 `apps/web/package.json` 的前端依赖。
- 基础设施沿用现有 `docker-compose.yml` 的 PostgreSQL，不替换 compose 文件，除非实现阶段发现必须做小范围补充。
