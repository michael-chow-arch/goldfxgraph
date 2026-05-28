## 1. 数据模型与持久化

- [ ] 1.1 在 `src/goldfxgraph/persistence/models.py` 中新增 `ForecastEvaluationModel`，补充 forecast 与 evaluation 的关联关系，并同步更新 `src/goldfxgraph/persistence/repositories.py` 的保存与查询接口。
- [ ] 1.2 在 `src/goldfxgraph/persistence/repositories.py` 中实现评估记录写入、历史反馈读取和按 forecast 查询 evaluation 的方法，确保研究运行、forecast、evaluation 三者可以追踪关联。
- [ ] 1.3 补充数据库迁移或建表初始化逻辑，确保新增 evaluation 表可以在本地与测试环境创建成功，并在 `tests/` 中覆盖基本持久化行为。
- [ ] 1.4 更新根目录 `.gitignore`，忽略 `.codex/spec/`、`superpower` 相关本地产物以及其他 OpenSpec 临时输出，避免误提交。

## 2. 收盘后评估与反馈任务

- [ ] 2.1 在 `src/goldfxgraph/workflow/nodes.py` 中实现 evaluation 计算辅助函数，基于后续 OHLC 数据计算方向命中、TP/SL 命中和收益点数，并输出结构化结果。
- [ ] 2.2 在 `src/goldfxgraph/backfill/eod_backfill.py` 或新增的调度模块中加入美国收盘后评估入口，支持按 `America/New_York` 时区自动运行并对“无当日 forecast”做空操作处理。
- [ ] 2.3 把 evaluation 结果回写到 `ForecastEvaluationModel`，并让 workflow 在下一次运行时可以读取最近的评估摘要与误差模式作为输入上下文。
- [ ] 2.4 为收盘后评估任务补充单元测试，覆盖 `skipped`、命中 TP/SL、同 bar 双触发的保守判定和无可用数据的降级情况。

## 3. 多 Agent workflow 扩展

- [ ] 3.1 在 `src/goldfxgraph/workflow/graph.py` 和 `src/goldfxgraph/workflow/nodes.py` 中接入历史反馈加载、市场情绪分析和另类数据分析节点，并确保节点命名与 spec 一致。
- [ ] 3.2 为 `agent_market_sentiment_analysis` 和 `agent_alt_data_analysis` 补充结构化输出路径，确保它们可以返回 summary、vote、confidence 和 unavailable 标记。
- [ ] 3.3 把历史 evaluation 摘要、市场情绪和另类数据信号接入 `agent_forecast_planning`，让最终 forecast 读取反馈上下文而不是只看当下价格与指标。
- [ ] 3.4 为 workflow graph 与新 agent 节点补测试，验证节点顺序、fallback 逻辑和结构化输出 contract。

## 4. API 与前端历史图表

- [ ] 4.1 在 `src/goldfxgraph/api/routes.py` 与 `src/goldfxgraph/schemas/forecast.py` 中加入 `GET /api/v1/forecast/history` 所需的 response schema 与路由实现。
- [ ] 4.2 在 `src/goldfxgraph/persistence/repositories.py` 中实现供 Dashboard 使用的历史 forecast / evaluation 查询方法，并确保返回按时间排序的结构化记录。
- [ ] 4.3 扩展 `apps/web/src/types/forecast.ts`、`apps/web/src/services/forecastApi.ts` 和 `apps/web/src/constants/forecast.ts`，支持历史记录类型、图表字段和空状态文案。
- [ ] 4.4 在 `apps/web/src/pages/GoldForecastDashboard.vue` 中新增历史表现图表与日度结果回看区域，展示日期、direction、entry、收益点数和 evaluation 结论。

## 5. 验证与收尾

- [ ] 5.1 在 `tests/` 中补齐 API、持久化、workflow 和 evaluation 的回归测试，覆盖新增 contract 与主要失败路径。
- [ ] 5.2 运行后端检查与测试，包括 `pytest`、`ruff check .` 和必要的单测定位修复。
- [ ] 5.3 进入 `apps/web/` 运行 `npm run lint`、`npm run typecheck` 和 `npm run build`，修复前端类型或构建错误。
- [ ] 5.4 复查 `openspec/changes/gold-forecast-feedback-loop/` 下的 proposal、design、specs 和 tasks，确认所有描述与实现范围一致后再进入 apply 阶段。

