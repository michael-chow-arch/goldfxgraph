# GoldFXGraph 预测反馈闭环实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 GoldFXGraph 从“单次预测输出”升级为“预测-评估-反馈-可视化”的研究闭环：每次 forecast 落库、每日收盘后自动评估当日预测、将评估结论回流到后续预测，并在前端展示历史表现图表和收益点数。

**Architecture:** 后端沿着现有 FastAPI / LangGraph / PostgreSQL 边界扩展，新增 evaluation 持久化层、收盘后评估调度、历史反馈读取和市场情绪/另类数据 agent 节点；前端保持 Vue 3 + TypeScript + Tailwind 的既有结构，只增加历史表现数据查询和图表展示。`.gitignore` 只补本地产物过滤，不改变 OpenSpec 结构或运行时 contract。

**Tech Stack:** Python 3.12, FastAPI, LangGraph, SQLAlchemy, PostgreSQL, Pydantic v2, pytest, ruff, Vue 3, TypeScript, Vite, Tailwind CSS.

---

## File Structure

- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/persistence/models.py`: 增加 `ForecastEvaluationModel`，并把 forecast 与 evaluation 的关系显式化。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/persistence/repositories.py`: 增加 evaluation 写入、历史反馈读取和历史表现查询接口。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/schemas/forecast.py`: 扩展 API response schema，加入历史表现和 evaluation 结构化字段。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/api/routes.py`: 新增 `GET /api/v1/forecast/history`，并确保返回空数据时语义清晰。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/workflow/graph.py`: 接入历史反馈、市场情绪与另类数据节点，并保持节点命名和顺序稳定。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/workflow/nodes.py`: 新增 evaluation 计算辅助函数、反馈读取和 sentiment / alt-data agent 节点。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/backfill/eod_backfill.py`: 扩展为收盘后评估入口，或拆分出独立 evaluation 调度逻辑。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/backfill/cli.py`: 提供可由调度器调用的收盘后任务入口。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/cli.py`: 连接统一 CLI 入口，方便后续部署与调度。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/packages/common/settings.py`: 如需增加收盘窗口、反馈查询窗口或另类数据源配置，在此集中定义。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/apps/web/src/services/forecastApi.ts`: 增加历史 forecast / evaluation 查询接口。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/apps/web/src/types/forecast.ts`: 扩展历史表现与 evaluation 的前端类型。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/apps/web/src/constants/forecast.ts`: 补充历史图表文案、状态文案和 agent 标签。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/apps/web/src/pages/GoldForecastDashboard.vue`: 增加历史表现图表与日度回看区域。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/.gitignore`: 忽略 `.codex/spec/`、`superpower` 相关本地生成内容。
- Create `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_forecast_evaluation_persistence.py`: 覆盖 evaluation 模型、仓储写入与历史查询。
- Create `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_forecast_evaluation_scheduler.py`: 覆盖收盘后评估的计算逻辑、跳过逻辑和保守判定。
- Create `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_forecast_history_api.py`: 覆盖 `/api/v1/forecast/history` 的响应、空态和结构化字段。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_workflow.py` 或新增 workflow 测试文件：覆盖 feedback / sentiment / alt-data 节点接入和 fallback 行为。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/apps/web/src/pages/` 及相关前端测试位置，如仓库已有前端测试约定则补齐历史图表的类型检查与构建验证。

## 1. 数据模型与持久化

**目标：** 让 forecast、research run 和 evaluation 三者在数据库中形成可追踪闭环，且历史表现能被稳定查询。

**Files:**
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/persistence/models.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/persistence/repositories.py`
- Create `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_forecast_evaluation_persistence.py`

- [ ] **Step 1: 先写 evaluation 持久化的失败测试**

  在 `tests/test_forecast_evaluation_persistence.py` 里先补一个最小失败用例，覆盖以下行为：

  - `ForecastEvaluationModel` 可以被导入
  - `ForecastRepository.save_forecast_evaluation(...)` 能保存 evaluation
  - `ForecastRepository.get_forecast_history(...)` 能返回按时间排序的历史记录

  运行：

  ```bash
  pytest tests/test_forecast_evaluation_persistence.py -q
  ```

  预期：当前应失败，因为 evaluation 模型和仓储方法还未实现。

- [ ] **Step 2: 实现数据库模型和仓储接口**

  在 `src/goldfxgraph/persistence/models.py` 中新增 `ForecastEvaluationModel`，建议字段至少包括：

  - `id`
  - `forecast_id`
  - `run_id`
  - `evaluated_at`
  - `evaluation_window_end`
  - `result`
  - `direction_hit`
  - `pnl_points`
  - `settlement_price`
  - `summary`
  - `feedback_notes`

  在 `src/goldfxgraph/persistence/repositories.py` 中新增对应方法，至少包含：

  - `save_forecast_evaluation(forecast_id: int, evaluation: ForecastEvaluationResult) -> ForecastEvaluationResult`
  - `get_forecast_evaluations(forecast_id: int) -> list[ForecastEvaluationResult]`
  - `get_forecast_history(limit: int = 50) -> list[ForecastHistoryItem]`
  - `get_latest_evaluation_summary(limit: int = 5) -> list[str]`

  实现时保持现有 `ResearchRunModel` / `ForecastModel` 结构不变，只做增量扩展。

- [ ] **Step 3: 让测试通过并复查字段名一致性**

  重新运行：

  ```bash
  pytest tests/test_forecast_evaluation_persistence.py -q
  ```

  预期：通过。

  然后检查仓储返回的结构是否与 OpenSpec 一致，特别是：

  - `direction`
  - `entry_price`
  - `take_profit_price`
  - `stop_loss_price`
  - `pnl_points`
  - `summary`
  - `feedback_notes`

- [ ] **Step 4: 补 `.gitignore`**

  在 `.gitignore` 中追加本地规范产物过滤规则，至少忽略：

  ```gitignore
  .codex/spec/
  .codex/spec/**
  **/superpower/
  **/superpowers/
  ```

  如果仓库里已有类似规则，保持统一风格，不要重复或误删现有通配项。

## 2. 收盘后评估与反馈回流

**目标：** 让系统在美国市场收盘后自动评估当日 forecast，并把评估结论作为后续预测的显式上下文。

**Files:**
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/workflow/nodes.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/backfill/eod_backfill.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/backfill/cli.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/cli.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/packages/common/settings.py`
- Create `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_forecast_evaluation_scheduler.py`

- [ ] **Step 1: 先写收盘评估逻辑的失败测试**

  在 `tests/test_forecast_evaluation_scheduler.py` 里覆盖以下场景：

  - 当日无 forecast 时返回 `skipped`
  - bullish forecast 触发 take-profit 时记录正向收益点数
  - bearish forecast 触发 stop-loss 时记录负向收益点数
  - 同一根 bar 同时触及 TP/SL 时采用保守规则

  运行：

  ```bash
  pytest tests/test_forecast_evaluation_scheduler.py -q
  ```

  预期：先失败。

- [ ] **Step 2: 实现 evaluation 计算辅助函数**

  在 `src/goldfxgraph/workflow/nodes.py` 中补充结构化辅助函数，用于：

  - 读取当日 forecast
  - 基于后续 OHLC 数据计算是否命中 TP / SL
  - 计算 `pnl_points`
  - 生成可写回数据库的 evaluation summary

  评估计算要保持 deterministic，不能依赖自由文本或 LLM 输出。

- [ ] **Step 3: 实现收盘后任务入口与反馈读取**

  在 `src/goldfxgraph/backfill/eod_backfill.py` 或独立模块中加入调度入口，支持：

  - 按 `America/New_York` 时区触发
  - 读取当日 forecast
  - 生成 evaluation
  - 写回仓储
  - 在无数据时返回 `no-op` 或 `skipped`

  然后在 `src/goldfxgraph/backfill/cli.py` 和 `src/goldfxgraph/cli.py` 中暴露统一命令入口。

  如果需要新配置项，优先放到 `src/goldfxgraph/packages/common/settings.py`，例如收盘缓冲窗口或默认回看天数。

- [ ] **Step 4: 让测试通过并补反馈摘要读取**

  再次运行：

  ```bash
  pytest tests/test_forecast_evaluation_scheduler.py -q
  ```

  预期：通过。

  同时确认下一轮 forecast planning 可以读取最近 evaluation 的摘要或误差模式，且在没有反馈时能优雅降级为默认上下文。

## 3. 多 Agent workflow 扩展

**目标：** 在现有技术 / 宏观 / 新闻 / 风险节点之外，加入历史反馈、市场情绪和另类数据分析能力，并把它们纳入最终 forecast planning。

**Files:**
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/workflow/graph.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/workflow/nodes.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/schemas/forecast.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/persistence/repositories.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_workflow.py` 或新增 workflow 测试文件

- [ ] **Step 1: 先写 workflow 节点接入的失败测试**

  在现有 workflow 测试里补充节点命名和执行顺序断言，至少覆盖：

  - `tool_load_forecast_feedback_history`
  - `tool_fetch_market_sentiment_inputs`
  - `tool_fetch_alt_data_inputs`
  - `agent_market_sentiment_analysis`
  - `agent_alt_data_analysis`

  运行：

  ```bash
  pytest tests/test_workflow.py -q
  ```

  预期：先失败，因为节点和 state 还未扩展。

- [ ] **Step 2: 增加反馈 / 情绪 / 另类数据状态字段**

  在 `WorkflowState` 和相关 Pydantic 模型里增加必要字段，至少包括：

  - `forecast_feedback_history`
  - `market_sentiment_summary`
  - `alt_data_summary`
  - `market_sentiment_votes`
  - `alt_data_votes`
  - `unavailable_signals`

  保持现有 `agent_votes`、`risk_notes` 和 `forecast` contract 不变。

- [ ] **Step 3: 实现 tool 和 agent 节点**

  在 `src/goldfxgraph/workflow/nodes.py` 中补齐：

  - `tool_load_forecast_feedback_history`
  - `tool_fetch_market_sentiment_inputs`
  - `tool_fetch_alt_data_inputs`
  - `agent_market_sentiment_analysis`
  - `agent_alt_data_analysis`

  这些节点要遵循职责分离：

  - tool 节点只采集结构化输入
  - agent 节点只解释输入并输出 summary / confidence / vote

  对于美国披萨指数这类另类数据，若来源不可用，应显式返回 `unavailable`，不要伪造数值。

- [ ] **Step 4: 把反馈和新信号接入 forecast planning**

  在 `agent_forecast_planning` 中融合：

  - 技术分析
  - 宏观分析
  - 新闻分析
  - 风险分析
  - 市场情绪
  - 另类数据
  - 历史 evaluation 反馈

  最终输出仍然必须保持结构化 forecast contract：

  - `direction`
  - `entry_price`
  - `take_profit_price`
  - `stop_loss_price`
  - `holding_period`
  - `intraday_action`
  - `long_term_action`
  - `confidence_score`
  - `risk_notes`

- [ ] **Step 5: 让 workflow 测试通过**

  再次运行：

  ```bash
  pytest tests/test_workflow.py -q
  ```

  预期：通过，且 fallback 路径在缺少情绪或另类数据时不会阻塞主流程。

## 4. API 与前端历史表现图表

**目标：** 为 Dashboard 提供历史 forecast / evaluation 查询接口，并在 Vue 页面中展示历史表现、收益点数和日度回看。

**Files:**
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/api/routes.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/schemas/forecast.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/persistence/repositories.py`
- Create `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_forecast_history_api.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/apps/web/src/services/forecastApi.ts`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/apps/web/src/types/forecast.ts`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/apps/web/src/constants/forecast.ts`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/apps/web/src/pages/GoldForecastDashboard.vue`

- [ ] **Step 1: 先写 history API 的失败测试**

  在 `tests/test_forecast_history_api.py` 中覆盖：

  - `GET /api/v1/forecast/history` 返回结构化历史记录
  - 数据为空时返回明确 empty 语义
  - 字段包含 direction、entry、收益点数、evaluation 结论和时间戳

  运行：

  ```bash
  pytest tests/test_forecast_history_api.py -q
  ```

  预期：先失败。

- [ ] **Step 2: 实现后端历史查询与 API schema**

  在 `src/goldfxgraph/schemas/forecast.py` 中加入历史条目 schema，例如：

  - `ForecastHistoryItem`
  - `ForecastEvaluationResult`
  - `ForecastHistoryResponse`

  在 `src/goldfxgraph/api/routes.py` 中新增 `GET /api/v1/forecast/history`。

  在 `src/goldfxgraph/persistence/repositories.py` 中实现排序查询，确保前端拿到的是可直接绘图的数据，而不是原始表记录。

- [ ] **Step 3: 扩展前端 service 和类型**

  在 `apps/web/src/types/forecast.ts` 中补充历史表现类型，在 `apps/web/src/services/forecastApi.ts` 中增加 `fetchForecastHistory()`。

  如果需要新的图表文案或 agent label，一并放到 `apps/web/src/constants/forecast.ts`，不要把文案散落在 Vue 模板里。

- [ ] **Step 4: 在 Dashboard 中增加历史表现图表**

  在 `apps/web/src/pages/GoldForecastDashboard.vue` 增加一个独立的历史表现区域，至少展示：

  - 日期
  - direction
  - entry_price
  - take_profit / stop_loss
  - `pnl_points`
  - evaluation 结论

  页面应保持当前 dark research cockpit 风格，并继续区分：

  - 最新 forecast
  - 历史表现
  - 研究摘要
  - 风险提示

- [ ] **Step 5: 运行前端验证**

  运行：

  ```bash
  cd /Users/admin/.codex/worktrees/e438/goldfxgraph/apps/web
  npm run typecheck
  npm run build
  ```

  预期：通过，且历史图表在空数据场景下显示清晰 empty state。

## 5. 收尾验证与计划对照

**目标：** 在提交前把 spec 约束和代码变更逐项对齐，避免漏改或越界。

**Files:**
- Review `/Users/admin/.codex/worktrees/e438/goldfxgraph/openspec/changes/gold-forecast-feedback-loop/proposal.md`
- Review `/Users/admin/.codex/worktrees/e438/goldfxgraph/openspec/changes/gold-forecast-feedback-loop/design.md`
- Review `/Users/admin/.codex/worktrees/e438/goldfxgraph/openspec/changes/gold-forecast-feedback-loop/specs/**/*.md`
- Review `/Users/admin/.codex/worktrees/e438/goldfxgraph/openspec/changes/gold-forecast-feedback-loop/tasks.md`

- [ ] **Step 1: 运行后端测试和 lint**

  运行：

  ```bash
  pytest
  ruff check .
  ```

  如果仓库当前测试体量较大，可以先跑与本次变更直接相关的测试文件，再补跑全量测试。

- [ ] **Step 2: 回顾 spec 覆盖**

  对照 OpenSpec change 的要求检查实现覆盖：

  - `forecast-evaluation-feedback-loop`
  - `market-sentiment-alt-data-analysis`
  - `backend-research-api`
  - `forecast-persistence`
  - `langgraph-forecast-workflow`
  - `gold-forecast-dashboard`

  确认每个 requirement 都有对应代码路径和测试。

- [ ] **Step 3: 复查 diff 并整理提交边界**

  使用下面的命令复查改动边界：

  ```bash
  git -C /Users/admin/.codex/worktrees/e438/goldfxgraph diff --stat
  git -C /Users/admin/.codex/worktrees/e438/goldfxgraph diff
  ```

  重点检查：

  - 没有把自动交易、券商集成或 mock market data 混进来
  - `.gitignore` 只过滤本地产物，不影响正式 spec
  - 前端没有把 API URL 硬编码进 Vue 组件
  - 新增 evaluation / sentiment / alt-data 逻辑仍然是结构化输出

