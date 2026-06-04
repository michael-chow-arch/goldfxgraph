# GoldFXGraph Dashboard Override

## 页面目标

Dashboard 是 GoldFXGraph 的主战场，必须像专业的 AI-native financial research cockpit，而不是普通报表页或普通交易页。

这个页面要优先让用户理解：

1. 当前 XAUUSD 怎么看
2. 为什么这么看
3. 接下来怎么执行
4. 研究过程是否可信
5. workflow 和 validation 是否完成

## 页面信息架构

### Section 1: Decision Summary

首屏必须展示：

- `current_price`
- `direction`
- `confidence_score`
- `reference_time`
- `data_timestamp`
- `data_source`
- `symbol`

### Section 2: Execution Plan

紧接着展示：

- `entry_price`
- `take_profit_price`
- `stop_loss_price`
- `risk_reward_ratio`
- `holding_period`
- `intraday_action`
- `long_term_action`

### Section 3: Market Snapshot

再展示：

- `daily_open`
- `daily_high`
- `daily_low`
- `daily_close`
- 与 price 相关的关键变动摘要

### Section 4: Research Explanation

随后展示：

- `technical_summary`
- `macro_summary`
- `news_summary`
- `risk_summary`
- 如可用，显示 `market_sentiment_summary`
- 如可用，显示 `alt_data_summary`

### Section 5: LangGraph Workflow & Agent Reasoning

展示：

- workflow node timeline
- tool call summary
- agent reasoning
- checkpoint / validation
- human review / repair

### Section 6: Evidence & Scorecard

展示：

- `agent_votes`
- `evidence_package`
- `validation_status`
- `committee_decision`
- `risk_notes`

### Section 7: History / Trace

展示：

- recent research run summary
- latest status
- forecast history
- scorecard / evaluation summary

## Dashboard 视觉规则

- 背景必须深色，不能恢复到浅色默认后台。
- 页面应通过应用级左侧导航与其他 cockpit 页面保持统一入口。
- 主结论区必须最醒目。
- 证据和工作流轨迹必须比结论次一级。
- 长文本必须有更高行距，但不要占据首屏主位。
- 标签、状态、数字统一使用等宽字体或接近等宽的语义风格。
- 不允许使用与全局系统冲突的第二套卡片语言。
- 禁止浅色底 card、浅色 pill、浅色提示块作为默认样式出现在 Dashboard 中。

## Dashboard 文字规范

Dashboard 只允许使用全局 `MASTER.md` 中定义的 8 种文字角色，并按以下方式映射：

- 首屏主结论使用 `display-title`
- 每个区域标题使用 `section-heading`
- card 内小标题使用 `card-title`
- 解释性正文使用 `body-md`
- 辅助说明使用 `body-sm`
- 背景说明、时间、来源、key name 使用 `meta-label`，并默认采用金色文字样式，不再包裹成新的胶囊；`meta-label` 本身要足够清晰，不能像灰色注释字
- 数值、价格、百分比、阶段使用 `numeric`

### 禁止项

- 不要在 Dashboard 里出现新的字号系统。
- 不要为了视觉变化而在组件内单独写 `text-sm`, `text-xs`, `font-semibold`, `tracking-*` 组合当作最终方案。
- 不要让 label/title 看起来像按钮，也不要让按钮/pill 看起来像标题。
- 不要把一段本该属于正文的内容伪装成标题。
- 不要把 label / title 再包进新的 badge 或 pill，除非它本身明确承担状态语义。

## Dashboard 专用组件优先级

1. `DecisionSummaryCard`
2. `ExecutionPlanCard`
3. `MarketSnapshotCard`
4. `WorkflowTracePanel`
5. `EvidenceBundleCard`
6. `ValidationPanel`
7. `StateBanner`
8. `SkeletonBlock`

## Dashboard 状态规范

### Loading

- 首屏必须显示结构化 skeleton。
- 用户要知道正在等什么数据。

### Empty

- 必须提示“暂无 forecast”原因。
- 必须给出等待或触发研究的暗示。

### Error

- 错误块必须说明问题是行情、API、还是 research run。
- 必须提供重试或刷新动作。

### Stale

- 若 forecast 不是最新完成结果，必须显示 stale 标识。

### Partial

- 若某些 summary 缺失，允许局部降级显示，但不能让空白掩盖问题。

## Dashboard 排版原则

- 桌面端采用“上总览、中执行、下解释、再轨迹、最后验证”的顺序。
- 平板端采用双列布局，但决策区始终优先。
- 移动端采用单列堆叠，保证从上到下的阅读顺序不丢失。

## Dashboard 胶囊规范

Dashboard 页面只允许使用以下胶囊：

- `status-pill`
- `analysis-badge`
- `confidence-chip`
- `data-chip`
- `agent-state-chip`

### 胶囊职责

- `status-pill`：状态与阶段
- `analysis-badge`：语义分类与角标
- `confidence-chip`：置信度
- `data-chip`：首屏摘要
- `agent-state-chip`：workflow agent 状态

### 禁止项

- 不要在 Dashboard 中自行定义新的 capsule / pill / chip 风格。
- 不要把 card title 做成另一种胶囊，除非它明确承担状态语义。
- 同类信息必须在所有页面使用同一套胶囊皮肤和颜色语义，禁止一处黑底一处彩底一处浅底。
- 不要把同一个信息在多个胶囊类型中重复表达。

## Dashboard Card 规范

- 首屏核心区域使用 `card--hero` 语义。
- 章节内容使用 `card--surface`。
- 细粒度明细与历史列表使用 `card--embedded` 或 `card--flat`。
- card 标题优先文字，不优先胶囊。
- 只有“主判断 / 元数据 / evidence / validation / trace”这类分类型 card 才可在标题区域使用 badge。

## Dashboard 禁止项

- 不要让 workflow 轨迹挤到首屏主位。
- 不要把所有模块做成同样大小的卡片。
- 不要把 evidence 和 decision 混成一个视觉层。
- 不要把 chart 当装饰。
- 不要用大段 free-form 文本代替结构化字段。

## Dashboard 组件重用规则

- 优先复用全局 `MASTER.md` 定义的基础组件语义。
- Dashboard 专用组件只允许增加对 research cockpit 的表达，不允许引入另一套风格。
- 所有新的 card、panel、rail、chip、timeline 都必须先对齐本 override。
