## Context

当前 GoldFXGraph 的实时 XAUUSD quote 仍然混有 Gold API 旧候选源，`CurrentQuoteProvider` 会在默认候选里尝试 `api.gold-api.com`。这会导致研究、health check、API 和前端展示在某些情况下看起来“有数据”，但真实来源并不是 TradingView，和用户要求的“绝不允许用假数据”冲突。

本次变更的目标是把运行时 current/latest quote 完全收口到 TradingView 的 `https://www.tradingview.com/symbols/XAUUSD/` 页面数据，并在 TradingView 不可用时显式失败，不再静默切回旧源。历史 completed daily bars、指标计算、agent 分工和前端整体布局都不是本次改造的重点。

## Goals / Non-Goals

**Goals:**
- 将 current/latest XAUUSD quote 的唯一运行时来源统一为 TradingView。
- 移除 Gold API 的 runtime fallback 和默认候选 URL。
- 保持 `CurrentQuote`、API response、workflow 和 frontend 的结构化 contract 不变，只替换真实数据来源。
- TradingView 失败时显式报错或返回 unavailable，不生成伪造价格、时间戳或来源。
- 让 health check、research-run 和 dashboard 看到一致的来源语义。

**Non-Goals:**
- 不重写历史 completed daily bars 的来源策略。
- 不变更 agent 的角色拆分或 prompt 结构。
- 不引入新的行情聚合层或多源投票机制。
- 不实现自动交易或券商集成。

## Decisions

### 1. 以 TradingView 页面解析作为唯一实时 quote 入口
我们将直接从 TradingView XAUUSD 页面解析 current price、时间戳和符号信息，并将其包装为 `CurrentQuote`。对外仅暴露这一条实时来源链路。

**为什么选择它：**
- 用户明确指定了这个来源。
- TradingView 页面已经能提供实时报价和日内 bar 语义，满足 research-only 场景。
- 统一来源后，workflow、health check 和前端不会再因候选 URL 差异而产生歧义。

**备选方案：**
- 保留 Gold API 作为 fallback：不采用，因为会继续污染“最新”语义。
- 使用缓存 last known good：不采用，因为会把旧数据伪装成实时。

### 2. 删除 Gold API runtime fallback
`CurrentQuoteProvider` 不再维护默认候选 URL，也不允许在 TradingView 失败后切到 Gold API。运行时必须“成功拿到 TradingView quote”或“明确失败”二选一。

**为什么这样做：**
- 避免任何旧源继续悄悄进入研究结果。
- 减少前端和后端对“当前价格”语义的误判。

**备选方案：**
- 仅在诊断模式保留旧源：不采用，因为容易被误用，且和用户要求冲突。

### 3. 失败显式传播到 workflow / API / dashboard
TradingView 页面不可达、结构变化或解析失败时，系统将返回受控错误或 unavailable 状态，并把失败原因一路传递到 API 和前端。

**为什么这样做：**
- 研究系统宁可缺失，也不能展示错误最新价。
- 显式失败能快速暴露页面结构变化或网络问题。

**备选方案：**
- 用 completed daily bar close 兜底：不采用，因为那会把历史 bar 冒充实时 quote。

### 4. 保持历史日线与实时 quote 分离
实时 quote 的切换不会影响历史 completed daily bars 的存储和查询边界。`daily_bar` 仍然是独立的历史完成日线数据集，不能被 current quote 覆盖或回写。

**为什么这样做：**
- 历史数据和实时数据的时间粒度不同，应该保持语义清晰。
- 前端和评估逻辑能更可靠地区分“最新 quote”和“日线收盘”。

### 5. 统一 source label
API 和前端展示的来源文案统一标识 TradingView。任何对外展示的 `data_source` 都必须能追溯到 TradingView XAUUSD 页面，不能再显示 Gold API 作为实时来源。

**为什么这样做：**
- 一致的 source label 有助于用户理解数据来源。
- 也方便 health check、research-run 和 dashboard 做同口径展示。

## Risks / Trade-offs

- [TradingView 页面结构变化] → 通过固定 fixture、解析器单测和显式错误处理缓解。
- [实时 quote 可用率下降] → 接受这个代价，优先真实性而不是连续性。
- [去掉 fallback 后初期失败更明显] → 用 health check 提前暴露问题，避免误判为“系统正常”。
- [实时 quote 和 completed daily bar 数值不一致] → 这是正常现象，需要在前端明确区分。

## Migration Plan

1. 新增 TradingView-only quote provider 与解析器，并补充成功/失败 fixture。
2. 将 `tool_fetch_current_gold_quote`、health check 和 research-run 切换到新 provider。
3. 删除 Gold API 默认候选 URL 与 runtime fallback 逻辑，清理相关配置说明。
4. 更新 API response 与 dashboard 的来源标签，确保不再出现旧源名称。
5. 运行后端和前端测试，验证任何路径都不会把旧源误展示为实时 quote。
6. 如 TradingView 解析策略需要调整，优先修解析器，不恢复旧源 fallback。

## Open Questions

- TradingView 页面中哪一个字段最稳定地代表 current price，需要在实现时通过 fixture 再确认。
- 是否要在内部日志中保留被移除的 Gold API 候选源名称；当前倾向于不保留，以免混淆。
