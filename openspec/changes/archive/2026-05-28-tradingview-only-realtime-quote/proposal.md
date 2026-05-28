## Why

当前 GoldFXGraph 的实时金价链路仍然混用了多个来源，容易出现“前端看起来是最新，但实际数据来自旧源”的问题。用户已经明确要求：运行时实时 quote 只允许使用 TradingView 的真实页面数据，旧的 Gold API 路径必须完全移除，不能再作为运行时回退或展示来源。

## What Changes

- 将实时 XAUUSD quote 的唯一运行时来源统一为 TradingView 页面数据。
- 移除 Gold API 在运行时的默认候选源和回退逻辑。
- 确保 research workflow、health check、API response 和前端展示都只暴露 TradingView 真实来源。
- 当 TradingView 不可用时，系统显式报错或返回 unavailable，不再自动切换到旧源。
- 保留历史日线的既有来源策略不变，只收口实时 quote 部分。

## Capabilities

### New Capabilities

- `tradingview-realtime-quote`: 统一从 TradingView 页面获取实时 XAUUSD quote，并将其作为唯一运行时价格来源。

### Modified Capabilities

- `current-quote-discovery`: 删除 Gold API 默认 fallback，改为只认 TradingView。
- `backend-research-api`: 返回的实时价格来源字段统一反映 TradingView。
- `gold-forecast-dashboard`: 前端展示只显示 TradingView 作为实时价格来源，不再出现 Gold API。

## Impact

- 后端 `src/goldfxgraph/market_data/` 中的实时 quote provider、workflow 入口和 health check 都会受影响。
- `research-run`、`/api/v1/research-runs` 和 `/api/v1/forecast/latest` 的数据来源说明会统一。
- 前端 dashboard 的“实时价格快照”与“数据来源”展示会收敛到 TradingView。
- 需要补充测试，确保旧的 Gold API 路径不会再参与运行时数据获取。
