## Why

当前 Dashboard 已经能展示结构化预测结果，但视觉层级仍偏基础，缺少更贴近黄金研究场景的专业观感。与此同时，项目还缺少一个稳定的每日收市后补数流程，无法自动检查 `data/raw/xauusd_daily.csv` 是否存在日线缺口并补齐历史数据。

## What Changes

- 将黄金预测 Dashboard 重设计为更具研究感的深色金融面板，突出最新价格、方向、风险、agent 摘要与交易研究字段。
- 引入更清晰的视觉层级和信息分区，让核心结论、OHLC、风险与免责声明更容易快速扫读。
- 增加一个每日收市后的定时任务，在美国黄金市场收市后运行，检查 CSV 最新日期与应有交易日序列之间是否存在缺口。
- 当检测到缺失日线时，调用 agent-assisted 数据查询流程获取候选黄金数据，再做确定性校验后回写 CSV。
- 保留现有研究-only 边界，不引入自动交易、下单或券商集成。

## Capabilities

### New Capabilities
- `daily-market-data-backfill`: 每日收市后执行的补数能力，负责检查 CSV 日期连续性、发现缺失日线、通过 agent 辅助查询获取候选数据，并在验证通过后持久化回 CSV。

### Modified Capabilities
- `gold-forecast-dashboard`: 调整 Dashboard 的视觉风格、布局与信息密度，使其成为更专业的黄金研究仪表盘，同时继续展示当前预测结果与研究免责声明。

## Impact

- 前端 `apps/web/src/pages/GoldForecastDashboard.vue` 及相关样式、常量和组件会更新为新的视觉语言。
- 后端需要新增一个面向收市补数的定时任务入口，以及与 CSV 检查、缺口计算、agent 查询、数据校验和写回相关的服务代码。
- `data/raw/xauusd_daily.csv` 的读写流程会增加连续性校验与补数写回路径。
- 需要补充对应的 OpenSpec spec delta、设计说明和任务拆分，确保实现可审阅、可验证。
