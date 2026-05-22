## 1. 项目骨架与配置

- [x] 1.1 新增 `src/goldfxgraph/` 后端包结构，包含 `api`、`schemas`、`market_data`、`indicators`、`workflow`、`persistence`、`packages/common` 模块
- [x] 1.2 更新 `pyproject.toml` 后端依赖，加入 FastAPI、uvicorn 及实现所需的测试/类型检查支持
- [x] 1.3 新增 `src/goldfxgraph/packages/common/settings.py`，从环境变量和本地开发配置加载数据库、CSV、current quote provider、agent API 地址和 agent API key
- [x] 1.4 新增 `.env.example` 与 `dev.env`，只包含非敏感默认值和 placeholder，不提交真实 secret
- [x] 1.5 确认现有 `docker-compose.yml` PostgreSQL 可用于本地持久化，除必要补充外不替换文件

## 2. 市场数据与技术指标

- [x] 2.1 实现 XAUUSD 日线 CSV loader，支持配置路径、大小写兼容字段解析、必要字段校验、日期排序和 latest completed daily bar 输出
- [x] 2.2 增加 CSV loader 单元测试，覆盖成功读取、缺字段、排序、可选字段保留和现有 `data/raw/xauusd_d.csv` 兼容场景
- [x] 2.3 实现 current/latest gold quote provider 边界，支持可配置 HTTP 数据源并记录 `current_price`、`data_source`、`data_timestamp`
- [x] 2.4 实现 provider 未配置或失败时的受控错误，禁止用 mock 数据伪装真实报价
- [x] 2.5 实现基础技术指标计算模块，至少覆盖一组 SMA/EMA/RSI/ATR/MACD 中的基础指标，并对数据不足返回结构化不可用原因
- [x] 2.6 增加指标计算单元测试，验证确定性结果和数据不足场景

## 3. 结构化模型与 LangGraph Workflow

- [x] 3.1 定义 Pydantic request/response models，覆盖 research run、daily bar、current quote、indicators、agent summaries、agent votes 和 forecast 输出
- [x] 3.2 实现 LangGraph workflow state 与图构建，包含 specs 要求的 router/tool/agent 节点名
- [x] 3.3 实现 `router_validate_request`、`tool_load_market_data`、`tool_fetch_current_gold_quote`、`tool_compute_indicators` 等确定性节点
- [x] 3.4 实现技术、宏观、新闻、风险和最终预测规划 agent 节点，使用可配置 agent API 地址与 API key，并约束输出为结构化结果
- [x] 3.5 在最终 forecast 中生成 `direction`、`entry_price`、`take_profit_price`、`stop_loss_price`、`holding_period`、`intraday_action`、`long_term_action`、`confidence_score`、`risk_notes` 和 disclaimer
- [x] 3.6 增加 workflow/schema 测试，验证节点存在、结构化输出字段、direction 枚举和 research-only 限制

## 4. PostgreSQL 持久化

- [x] 4.1 实现 async SQLAlchemy engine/session 管理和显式 metadata 初始化边界
- [x] 4.2 实现 `ResearchRunModel` 与 `ForecastModel`，使用 `Model` suffix 并保存 specs 要求字段
- [x] 4.3 实现 repository/service 层，支持创建/更新 research run、保存 forecast、查询 latest forecast、按 run_id 查询 research run
- [x] 4.4 将 `tool_persist_research_run` 与 `tool_persist_forecast` 接入 workflow
- [x] 4.5 增加持久化测试，覆盖成功保存、失败状态记录、latest forecast 查询和 run_id 查询

## 5. FastAPI API

- [x] 5.1 实现 FastAPI app factory、健康检查或基础启动入口，并挂载 `/api/v1` router
- [x] 5.2 实现 `GET /api/v1/forecast/latest`
- [x] 5.3 实现 `POST /api/v1/research-runs`
- [x] 5.4 实现 `GET /api/v1/research-runs/{run_id}`
- [x] 5.5 实现 API 错误结构，覆盖市场数据错误、agent 调用错误、预测不存在和持久化错误
- [x] 5.6 增加 API 测试，验证结构化响应、empty/not found、错误响应和 secret 不泄露

## 6. Vue 3 + Tailwind 前端

- [ ] 6.1 在 `apps/web/` 新增 Vite + Vue 3 + TypeScript + Tailwind CSS 项目结构
- [ ] 6.2 新增 `apps/web/src/styles/main.css`，配置 Tailwind imports 与共享 base styles
- [ ] 6.3 新增 `apps/web/src/types/forecast.ts`，与后端 forecast contract 对齐
- [ ] 6.4 新增 `apps/web/src/services/forecastApi.ts`，从 `VITE_API_BASE_URL` 调用 FastAPI，不在 Vue 页面硬编码后端 URL
- [ ] 6.5 新增 router、constants 和 `GoldForecastDashboard.vue`，展示 current price、direction、confidence、OHLC、entry/take-profit/stop-loss、持有建议、agent summaries、votes、risk notes 和 disclaimer
- [ ] 6.6 实现 Dashboard loading、error、empty、success 状态和重试入口，不硬编码生产预测假数据
- [ ] 6.7 运行前端 typecheck/build，并用浏览器或截图检查 Dashboard 在桌面与移动视口下无明显重叠和布局问题

## 7. 验证与收尾

- [ ] 7.1 运行 `openspec validate bootstrap-fullstack-xauusd-forecast-dashboard --strict` 或当前 CLI 支持的等效校验
- [ ] 7.2 运行后端测试与检查：`pytest`、`ruff check .`、`ruff format --check .`、`pyright` 或项目实际可用命令
- [ ] 7.3 运行前端检查：`npm run typecheck`、`npm run build`，如配置了 lint 则运行 `npm run lint`
- [ ] 7.4 检查 git diff，确认未提交 secret、未引入自动交易/下单/券商/n8n/MCP/多模型路由/scorecard/完整评估系统
- [ ] 7.5 更新 `tasks.md` 勾选已完成项，并准备人工 review 后再 archive OpenSpec change
