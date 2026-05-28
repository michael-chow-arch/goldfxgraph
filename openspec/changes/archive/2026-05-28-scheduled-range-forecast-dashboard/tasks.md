## 1. 统一调度与状态模型

- [ ] 1.1 在 `src/goldfxgraph/persistence/models.py` 中新增统一调度运行状态模型，记录 `started_at`、`completed_at`、`current_stage`、`agent_statuses` 和 `last_error`。
- [ ] 1.2 在 `src/goldfxgraph/persistence/repositories.py` 中增加运行状态的写入、读取和更新方法，确保前端能查询最近一次执行情况。
- [ ] 1.3 在 `src/goldfxgraph/backfill/scheduler.py` 或新增调度模块中实现一个 15 分钟统一循环，把数据获取、当日更新和 agent 分析串成一个流程。
- [ ] 1.4 补充测试，覆盖统一调度循环的成功、失败、取消和状态更新场景。

## 2. 窗口化 forecast 输出

- [ ] 2.1 在 `src/goldfxgraph/schemas/forecast.py` 中新增窗口化方向数据结构，并扩展 `ForecastResult` 以包含固定时间窗口方向区间。
- [ ] 2.2 在 `src/goldfxgraph/workflow/nodes.py` 中改造 forecast planning 逻辑，让 agent 按固定窗口输出方向、强度、置信度和理由。
- [ ] 2.3 在 `src/goldfxgraph/workflow/graph.py` 中保持现有 agent 顺序与职责，但确保最终输出符合新的窗口化 contract。
- [ ] 2.4 增加 workflow 和 schema 的单元测试，验证窗口标签、方向枚举、置信度范围和结构化输出字段。

## 3. API 与前端状态展示

- [ ] 3.1 在 `src/goldfxgraph/api/routes.py` 中移除或禁用手工触发研究的路径，新增或扩展只读状态接口供前端查询。
- [ ] 3.2 在 `apps/web/src/types/forecast.ts` 和 `apps/web/src/services/forecastApi.ts` 中加入统一调度状态和窗口化 forecast 类型。
- [ ] 3.3 在 `apps/web/src/pages/GoldForecastDashboard.vue` 中重排首屏，展示当前价格、方向区间、入场/止盈/止损、最近执行时间和 agent 状态。
- [ ] 3.4 去掉页面中的手动刷新按钮，并改为读取最新 forecast 与最新运行状态，不再触发手工执行。

## 4. 保持既有分析模块

- [ ] 4.1 确认分析原因列表区域继续使用现有数据结构与展示顺序，不做功能性重写。
- [ ] 4.2 确认 `MarketCandlestickChart` 及其数据流保持不变。
- [ ] 4.3 确认最新市场新闻和情绪模块继续沿用现有服务与展示逻辑。

## 5. 验证与收尾

- [ ] 5.1 运行后端测试，覆盖持久化、调度、workflow 和 API contract 变化。
- [ ] 5.2 运行前端 `npm run lint`、`npm run typecheck` 和 `npm run build`，修复类型和构建问题。
- [ ] 5.3 复查 `openspec/changes/scheduled-range-forecast-dashboard/` 下的 proposal、design 和 tasks，确认描述与确认结果一致后再进入 apply 阶段。
