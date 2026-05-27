## Why

GoldFXGraph 目前已经具备基础预测与展示骨架，但预测结果还没有形成完整闭环：每次预测后的结构化结果需要稳定入库，收盘后也需要自动评判当日预测表现，并把这些结论作为后续预测的参考。与此同时，项目还缺少市场情绪和另类数据分析能力，无法让 agent 系统性地利用像美国披萨指数这类补充信号。

## What Changes

- 每次生成 forecast 后都持久化到 PostgreSQL，并保留可追踪的研究运行、预测结果和后续评估关联关系。
- 新增每日美国市场收盘后的定时评估任务，自动检查当日是否存在预测结果，并计算其后验表现、命中情况与利润点数等指标。
- 将每日评估结论写回数据库，作为后续预测的参考上下文，而不是只停留在一次性分析里。
- 新增或扩展用于市场情绪与另类数据的 agent 能力，包括美国披萨指数等外部信号的读取、解释和结构化输出。
- 补齐现有 workflow 中尚未覆盖的 agent 职责，让多 agent 分析覆盖技术、宏观、新闻、风险、情绪与另类数据等维度。
- 扩展前端 Dashboard，增加历史预测结果、日度表现、按预测点位计算的收益点数等图表化展示。
- 更新 `.gitignore`，忽略 `.codex/spec/`、`superpower` 相关本地生成内容，避免把临时规范产物提交到仓库。

## Capabilities

### New Capabilities

- `forecast-evaluation-feedback-loop`: 定义收盘后自动评估当日预测、计算表现指标、保存结论并向后续预测提供反馈的能力。
- `market-sentiment-alt-data-analysis`: 定义市场情绪与另类数据分析能力，包括美国披萨指数等外部信号的采集、结构化分析与 agent 输出。

### Modified Capabilities

- `forecast-persistence`: 将“每次预测后入库”扩展为保存研究运行、forecast、日度评估结果、历史表现指标和反馈引用关系。
- `backend-research-api`: 增加可供前端图表使用的历史结果/表现查询能力，并返回与反馈循环相关的结构化数据。
- `langgraph-forecast-workflow`: 扩展 multi-agent graph 的职责边界，接入情绪/另类数据 agent，并读取历史评估反馈作为推理上下文。
- `gold-forecast-dashboard`: 增加历史预测与日度表现图表，展示按预测点位计算的收益点数、胜率/命中类指标和评估摘要。

## Impact

- 后端会新增定时评估调度、评估结果模型、反馈读取逻辑和更多 agent 分析节点，涉及 `src/goldfxgraph/` 下的 workflow、service、scheduler、persistence 和 schema 模块。
- API 层需要补充历史表现查询能力，供前端 Dashboard 绘制图表和展示回测/评估结果。
- 前端 `apps/web/` 需要增加历史结果图表和性能摘要展示，并继续通过 typed service 读取后端数据。
- 数据库会新增或扩展研究运行、forecast 和 evaluation 相关表结构。
- 仓库根目录 `.gitignore` 需要新增本地规范产物过滤规则，避免提交 `.codex/spec/`、`superpower` 等目录内容。

