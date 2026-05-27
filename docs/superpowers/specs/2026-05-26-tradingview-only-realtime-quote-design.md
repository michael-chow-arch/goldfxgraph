# TradingView Only Realtime Quote Design

## Context

GoldFXGraph 当前的实时 XAUUSD 报价链路仍然混有旧的 Gold API 运行时候选源。用户已经明确要求：运行时实时 quote 只能来自 TradingView 的 `https://www.tradingview.com/symbols/XAUUSD/` 页面数据，不能再出现 Gold API 的自动回退、隐藏候选或“看起来像最新”的旧值。

现有系统中，`CurrentQuoteProvider` 仍然存在默认候选 URL，`tool_fetch_current_gold_quote`、agent health check、research-run 以及前端 dashboard 都依赖同一条 quote 线路。因此这次变更会跨越 market data、workflow、API、diagnostics 和 frontend，但本质上是单一目标：把实时 quote 彻底收口到 TradingView，并在失败时明确暴露 unavailable/错误状态。

历史 completed daily bars、指标计算、agent 分工和 dashboard 的其他研究字段不在这次改造的核心范围内。它们仍然保留，只是不再允许实时 quote 混入旧源。

## Goals / Non-Goals

**Goals:**
- 将 current/latest XAUUSD quote 的唯一运行时来源改为 TradingView 页面数据。
- 移除 Gold API 在 runtime discovery 中的所有默认候选和自动回退路径。
- 保持 `CurrentQuote`、API 响应和前端展示的结构化 contract 不变，只替换真实来源。
- 在 TradingView 不可用或解析失败时，显式失败，不生成伪造价格、伪造时间戳或伪造来源。
- 让 health check、research-run 和 dashboard 都能一致暴露 TradingView 作为实时来源。

**Non-Goals:**
- 不重构历史 completed daily bars 的数据源策略。
- 不改写 agent 的业务分工或 prompt 结构。
- 不实现自动交易、券商接单或额外行情回退网络。
- 不在本次变更里重新设计前端整体视觉，只调整来源与状态显示。

## Decisions

### 1. TradingView 页面解析作为唯一实时 quote 入口
我们采用 TradingView 的 XAUUSD 页面作为唯一运行时 quote 来源。实现上会把“页面 HTML / 嵌入状态中的实时价格、时间戳、symbol 信息”解析成 `CurrentQuote`，并让 workflow、API 和 dashboard 都消费同一结构化对象。

**为什么这样做：**
- 这是用户指定的真实来源。
- TradingView 页面能同时提供当前价和日内状态，足以支撑 research-only 场景。
- 相比 Gold API，TradingView 入口更符合“单一可信来源”的要求。

**备选方案：**
- 保留 Gold API 作为备份：被拒绝，因为会继续引入旧源和真假混用风险。
- 使用内部缓存 last known good：被拒绝，因为会把旧价格伪装成最新数据。

### 2. 运行时彻底删除 Gold API fallback
`CurrentQuoteProvider` 不能再把 Gold API 当默认候选，也不能在 TradingView 失败后自动切换到别的公开报价源。若 TradingView 不可用，系统必须明确失败或标记 unavailable。

**为什么这样做：**
- 用户已经明确要求“决不允许用假数据”。
- 自动 fallback 会让前端和研究结果难以区分“实时”和“旧值”。
- 关闭 fallback 后，数据问题会更早暴露，便于定位和修复。

**备选方案：**
- 保留 Gold API 作为仅诊断使用的隐藏回退：被拒绝，因为仍然可能被误用并污染结果。

### 3. 将失败显式传递到 workflow / API / dashboard
如果 TradingView 页面不可达、结构变化或解析失败，系统不会伪造 quote，而是将失败状态显式传给 workflow 和 API，再让前端展示 unavailable 或结构化错误。

**为什么这样做：**
- 可观测性比“静默补值”更重要。
- 对研究系统来说，明确知道数据缺失比看到错误的“最新价格”更安全。

**备选方案：**
- 用 latest daily bar close 兜底：被拒绝，因为会混淆实时 quote 与 completed daily bar。

### 4. 保持历史 completed daily bars 与实时 quote 分离
这次变更只修改实时 quote。历史日线仍然是独立数据集，不把 TradingView quote 写回为历史完成日线，也不在 runtime 里把 completed bar 当成 current quote。

**为什么这样做：**
- `current/latest quote` 和 `completed daily bar` 是不同粒度的数据。
- 分离后，研究和复盘口径更清晰。

### 5. 统一 data_source 语义
API 和前端展示的 `data_source` 将统一反映 TradingView 的 XAUUSD 页面来源。业务上可以显示为“TradingView / XAUUSD”，但不能再出现 Gold API、旧候选 URL 或其他历史回退源作为实时来源。

**为什么这样做：**
- 统一来源标签能减少用户误解。
- 让 health check、research-run、最新 forecast、前端卡片看到同一条来源链路。

## Risks / Trade-offs

- [页面结构变化导致解析失败] → 通过固定 fixture、解析器单测和显式错误来缓解。
- [TradingView 短时不可用导致研究结果变少] → 这是接受的代价，优先保证真实性而不是连续性。
- [移除 fallback 后初期失败率上升] → 用 health check 提前暴露问题，并在 API 层给出可读错误，避免误判为“系统正常”。
- [实时 quote 与 completed daily bar 数值不一致] → 这是正常现象，因为两者来源与粒度不同，必须在展示上明确区分。

## Migration Plan

1. 先实现 TradingView-only quote provider 和解析器，补充成功/失败 fixture。
2. 把 `tool_fetch_current_gold_quote`、agent health check 和 research-run 切到新 provider。
3. 删除 Gold API 默认候选 URL、相关环境变量说明和运行时回退逻辑。
4. 更新 API response 与前端 `data_source` 文案，确保不再出现旧源。
5. 运行后端、前端和健康检查测试，确认任何场景都不会把旧源误展示为最新。
6. 如果 TradingView 解析出现新问题，回滚到上一版代码，而不是在 runtime 增加旧源回退。

## Open Questions

- 是否需要在日志中保留“曾经尝试过的旧源”诊断信息？当前建议不保留，以免误导。
- TradingView 页面中用于解析 current quote 的具体字段是否需要固定成单一抽取策略？当前建议先封装在 provider 内部，外部只看 `CurrentQuote`。
