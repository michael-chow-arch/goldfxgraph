## Why

当前 dashboard 已经具备完整的研究信息流，但视觉层级、卡片密度、响应式布局和状态展示仍偏“功能堆叠式”，不够像一个成熟的金融研究控制台。我们需要在不改变任何接口、字段和功能的前提下，把页面重构成更专业、更易扫读、更适合高频查看的研究面板。

## What Changes

- 重设计 dashboard 的首屏信息架构，突出当前价格、当日方向、置信度、最新执行时间和核心结论。
- 重构主要指标卡片、K 线图、结构化交易字段、摘要区、风险区和历史区的布局层级与信息密度。
- 统一卡片圆角、边框、阴影、间距、字体层级、状态标签和颜色系统，使页面呈现更高一致性与高级感。
- 优化 loading、empty、error、success 状态的视觉表达，避免空白面板和误导性展示。
- 强化移动端、平板端与桌面端的响应式布局，确保核心结论始终优先可见。
- 保持所有现有 API 调用、字段解析、类型契约、路由和业务功能完全不变。

## Capabilities

### New Capabilities
- 无：本次不新增业务能力，仅重设计现有 dashboard 的展示层。

### Modified Capabilities
- `gold-forecast-dashboard`: 调整 dashboard 的视觉层级、布局结构、卡片样式、信息密度、响应式体验、加载态、空状态与错误态的呈现方式，但不改变任何数据契约或功能行为。

## Impact

- 受影响代码主要集中在 `apps/web/src/pages/GoldForecastDashboard.vue`、`apps/web/src/components/MarketCandlestickChart.vue` 和 `apps/web/src/styles/main.css` 的展示层实现。
- 如有必要，仅允许调整展示用常量和局部组件拆分，不允许修改 API 路径、请求参数、响应字段名、类型字段名、store/query key 或路由逻辑。
- OpenSpec 需同步更新 `openspec/specs/gold-forecast-dashboard/spec.md` 的对应 requirements，确保视觉重设计仍受契约约束。
