## 1. 现状分析与契约梳理

- [x] 1.1 梳理当前 LangGraph workflow、state、agent、persistence、API 和 dashboard 的现有契约，确认哪些字段必须保持兼容。
- [x] 1.2 盘点 Trading Committee 相关 prompt、结构化输出和 repository 边界，明确哪些能力需要新增 spec delta，哪些只需实现层扩展。

## 2. 数据模型与 Prompt Registry

- [x] 2.1 设计并落地 `EvidencePackage`、`DebateCase`、`DebateRebuttal`、`FinalDebatePosition`、`CommitteeDecision`、`ValidationResult` 和 `FinalForecast` 的 Pydantic schema。
- [x] 2.2 新增 `PromptTemplateModel` 与最小可行的 Prompt Registry / PromptTemplateService，支持 `get_active_prompt`、`validate_required_variables` 和 `render_prompt`。
- [x] 2.3 为 Trading Committee 默认 prompt 编写 seed data，包含 `prompt_text_en`、`prompt_text_zh`、`prompt_key`、`version`、`prompt_type` 和 active 标记。

## 3. Workflow 与 Committee 实现

- [x] 3.1 将 workflow 重构为“specialist analysis -> evidence package -> opening -> rebuttal -> final position -> chair -> validation -> repair -> persist”的固定拓扑。
- [x] 3.2 实现 `node_build_evidence_package`，并确保它只消费已完成的 specialist 结果，不允许绕过 evidence package 直接进入委员会决策。
- [x] 3.3 实现 `agent_bull_opening_case`、`agent_bear_opening_case`、`agent_bull_rebuttal`、`agent_bear_rebuttal`、`agent_bull_final_position`、`agent_bear_final_position`、`agent_trading_committee_chair` 和 `agent_repair_committee_decision`，并通过 Prompt Registry 读取 prompt。
- [x] 3.4 实现 `node_validate_committee_decision` 的规则校验与 repair routing，限制 repair 次数并在失败时标记 workflow 失败。

## 4. 持久化与 API

- [x] 4.1 扩展 persistence models/repositories，保存 evidence package、debate rounds、committee decision、validation status、prompt_key 和 prompt_version metadata。
- [x] 4.2 更新 FastAPI response schema，新增 committee trace 与 metadata 字段，同时保持既有 dashboard 依赖字段不被破坏。
- [x] 4.3 确认 `GET /api/v1/forecast/latest`、`POST /api/v1/research-runs` 和 `GET /api/v1/research-runs/{run_id}` 的兼容行为与空值/失败行为。

## 5. Dashboard 展示

- [x] 5.1 更新 `apps/web/src/types/forecast.ts` 与 `apps/web/src/services/forecastApi.ts`，对接新增 committee 字段与 prompt metadata。
- [x] 5.2 在 `apps/web/src/pages/GoldForecastDashboard.vue` 中新增 Evidence Package、Trading Committee Debate、Committee Chair Decision、Validation Status、Prompt Version Metadata 和 Graph Execution Trace 区域。
- [x] 5.3 保持现有核心价格、方向、交易字段与免责声明布局稳定，不引入 prompt 管理后台或 hard-coded prompt 内容。

## 6. 测试与文档

- [x] 6.1 增加 Prompt Registry 测试，覆盖 `get_active_prompt`、`render_prompt`、`validate_required_variables`、missing variable error 和 inactive version 不默认加载。
- [x] 6.2 增加 committee workflow 测试，覆盖 evidence package 等待、opening / rebuttal / final / chair 的依赖顺序、validator 失败后的 repair routing。
- [x] 6.3 增加 decision validator 测试，覆盖 bullish / bearish / range_bound / cautious 的必需字段、confidence 范围、low confidence trade_candidate 拒绝和风险收益约束。
- [x] 6.4 更新 README / docs，说明 Two-Round Adversarial Trading Committee 与 Prompt Registry 的工作方式和 research-only 定位。
- [x] 6.5 运行后端与前端相关 lint / typecheck / test / build 检查，修复与新 contract 相关的回归。
