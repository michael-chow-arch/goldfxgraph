## Context

当前仓库处于早期阶段：已有项目说明、`pyproject.toml`、PostgreSQL `docker-compose.yml` 和 `data/raw/xauusd_d.csv`，但没有 `src/goldfxgraph/` 后端实现、`tests/`、`apps/web/` 前端项目或已生效 OpenSpec specs。本次变更需要建立第一版可运行的端到端研究能力，同时遵守项目限制：使用真实数据，不做自动交易、下单、券商接入、n8n、MCP、多模型路由、scorecard、完整评估系统或复杂 observability。

主要使用者是需要查看 XAUUSD 研究结果的本地用户。后端负责读取真实日线 CSV、按需获取 current/latest 金价、计算指标、运行 LangGraph 多 Agent workflow、保存研究运行与预测结果；前端负责通过 API 展示最新预测 Dashboard。

## Goals / Non-Goals

**Goals:**

- 建立 `src/goldfxgraph/` 下的 FastAPI 后端，提供第一版研究 API。
- 建立 `dev.env` 与 `.env.example` 配置约定，支持配置 agent API 地址、agent API key、数据库 URL、CSV 路径、current quote 数据源等。
- 读取并验证用户提供的 XAUUSD 日线 CSV，输出 latest completed daily bar。
- 按需获取 current/latest 金价，并在预测结果中记录数据来源和时间。
- 计算第一版基础技术指标，作为结构化 workflow 输入。
- 使用显式 LangGraph 节点组织 router/tool/agent 流程，生成 Pydantic 结构化预测结果。
- 使用 PostgreSQL 保存 research run 与 forecast。
- 新增 `apps/web/` Vue 3 + TypeScript + Vite + Tailwind CSS Dashboard，通过 typed service 调用 FastAPI。
- 增加可直接运行的后端和前端验证命令与测试。

**Non-Goals:**

- 不实现自动交易、真实下单、券商接入或交易账户连接。
- 不实现 n8n、MCP、多模型路由、scorecard、完整评估系统、复杂 observability。
- 不引入复杂数据库迁移体系；第一版可以用显式 SQLAlchemy metadata 初始化边界。
- 不在生产 Dashboard 中硬编码预测假数据。
- 不承诺提供投资建议；输出必须是研究和决策支持。

## Decisions

### FastAPI 模块边界

后端按领域拆分为 `packages/common/settings.py`、`api/`、`schemas/`、`market_data/`、`indicators/`、`workflow/`、`persistence/`。API 层只处理 HTTP 请求和响应，业务流程由 service/workflow 层完成。

Alternatives considered: 把所有逻辑放在单个 `main.py` 中实现更快，但会让 CSV 校验、指标、workflow、持久化互相缠绕，不利于测试和后续扩展。

### 配置与 secrets

新增 committed `dev.env` 作为本地开发配置模板或非敏感默认值，新增 `.env.example` 作为环境变量说明。真实 secret 不提交；`agent_api_key` 从环境变量读取，并在日志和响应中避免泄露。

Alternatives considered: 只使用 `.env.example` 更简单，但用户明确要求增加/更换 `dev.env`；把 API key 写入代码或前端不可接受。

### 市场数据策略

日线历史数据以用户 CSV 为第一版主数据源，默认路径配置为 `data/raw/xauusd_daily.csv`，同时实现对仓库现有 `data/raw/xauusd_d.csv` 的兼容或在文档/配置中明确默认路径。CSV loader 必须大小写兼容地验证 `date/open/high/low/close`，排序后选取最新完成日线 bar。

current/latest 金价通过可配置 provider 获取。第一版优先实现 HTTP provider 的接口边界，并允许当 provider 未配置或失败时返回清晰错误；不得用 mock 数据替代主 workflow 的真实数据。

Alternatives considered: 直接用 CSV close 当作 current price 可以让流程更容易跑通，但会混淆 completed daily bar 与 current/latest quote，不符合数据规则。

### 技术指标

第一版指标保持确定性和可测试：SMA、EMA、RSI、ATR、MACD 或其中基础集合，输入来自已验证日线数据。指标模块不调用 LLM，不依赖自由文本。

Alternatives considered: 引入完整 TA 库能更快覆盖大量指标，但增加依赖和语义不透明；第一版优先可控实现。

### LangGraph workflow

workflow 使用明确节点名：

- `router_validate_request`
- `tool_load_market_data`
- `tool_fetch_current_gold_quote`
- `tool_compute_indicators`
- `agent_technical_analysis`
- `agent_macro_analysis`
- `agent_news_analysis`
- `agent_risk_analysis`
- `agent_forecast_planning`
- `tool_persist_research_run`
- `tool_persist_forecast`
- `router_finalize_result`

tool 节点做确定性工作，agent 节点生成结构化分析摘要和投票，router 节点做校验和最终输出整理。agent 调用使用可配置 `GOLDFXGRAPH_AGENT_API_BASE_URL` 与 `GOLDFXGRAPH_AGENT_API_KEY`；第一版不做多模型路由。

Alternatives considered: 使用普通 Python service 顺序调用最简单，但用户明确要求 LangGraph 多 Agent；使用复杂并行图和 checkpointing 会超出第一版范围。

### 结构化预测模型

预测输出使用 Pydantic models，至少包含 `symbol`、`reference_time`、`data_timestamp`、`data_source`、`current_price`、日线 OHLC、`direction`、`entry_price`、`take_profit_price`、`stop_loss_price`、`holding_period`、`intraday_action`、`long_term_action`、`confidence_score`、各 agent summary、`agent_votes`、`risk_notes` 和 disclaimer。`direction` 使用 `bullish/bearish/neutral`，前端映射为 `看多/看空/震荡/中性`。

Alternatives considered: 只返回自然语言报告更快，但不满足 Dashboard、持久化和后续扩展需要。

### PostgreSQL 持久化

使用 SQLAlchemy async ORM 和现有 PostgreSQL compose。ORM 类名使用 `ResearchRunModel` 与 `ForecastModel`。持久化边界显式注册 metadata，不使用 string-based dynamic imports。

Alternatives considered: SQLite 更轻，但项目要求 PostgreSQL；完整 Alembic 迁移体系更成熟，但第一版可以先不引入复杂迁移。

### Frontend Dashboard

前端使用 `apps/web/`，Vue 3 Composition API、TypeScript、Vite、Tailwind。API base URL 来自 `VITE_API_BASE_URL`，typed service 位于 `apps/web/src/services/forecastApi.ts`，types 位于 `apps/web/src/types/forecast.ts`。Dashboard 首屏就是研究结果，不做营销 landing page。

页面以工作型 Dashboard 组织：顶部显示 current price、direction、confidence、data source/time；中部清晰分离 entry/take-profit/stop-loss、holding advice、daily OHLC；下方展示 multi-agent summaries、agent votes、risk notes 和免责声明。包含 loading、error、empty、success 状态。

Alternatives considered: 使用静态假数据可以更快完成 UI，但违反前端要求；引入大型 UI 组件库会增加初始复杂度。

## Risks / Trade-offs

- [Risk] current/latest 金价 provider 可能需要外部 API key 或网络权限。→ Mitigation: provider 配置显式化，失败时返回可诊断错误，并把 completed daily bar 与 current quote 分开记录。
- [Risk] LLM/agent 输出可能格式不稳定。→ Mitigation: 使用 Pydantic schema、结构化 prompt、解析失败处理和可测试 fallback 错误，不把自由文本直接当最终结果。
- [Risk] 第一版没有完整迁移系统会限制生产部署。→ Mitigation: 将 schema 初始化封装在 persistence 边界，后续可引入 Alembic 而不改变 API contract。
- [Risk] Dashboard 可能因为 API 不可用而空白。→ Mitigation: 实现 loading/error/empty 状态和重试入口，避免硬编码假数据。
- [Risk] agent API key 属于 secret。→ Mitigation: 只通过环境变量读取，不提交真实值，不返回给前端。

## Migration Plan

1. 新增 OpenSpec specs 并通过 `openspec validate`。
2. 实现时先搭建后端包结构、settings、schemas 和 CSV/indicator 单元测试。
3. 接入 FastAPI、workflow 和 persistence，再补 API 测试。
4. 新增前端项目和 Dashboard，使用 typed API service 接入后端。
5. 运行 `pytest`、`ruff check .`、`ruff format --check .`、`pyright` 或项目实际命令，以及前端 `npm run typecheck`、`npm run build`。

Rollback strategy: 本次为新增能力，若实现失败，可回退新增后端模块、`apps/web/` 和 OpenSpec change，不影响现有 README、CSV 和 PostgreSQL compose 的基本状态。

## Open Questions

- current/latest 金价第一版应接入哪个具体 provider 需要在实现时根据可用 API key 和用户本地网络条件确定；spec 仅要求 provider 可配置、来源和时间可记录、失败可诊断。
- `dev.env` 是否作为可直接加载文件还是示例开发文件，需在实现时与 `python-dotenv` 加载顺序保持一致；不得包含真实 secret。
