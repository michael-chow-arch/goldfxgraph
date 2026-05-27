## 1. TradingView 实时报价收口

- [ ] 1.1 新增 TradingView 解析器并移除 `CurrentQuoteProvider` 的 Gold API 默认候选 URL，确保 runtime 只会读取 `https://www.tradingview.com/symbols/XAUUSD/`
- [ ] 1.2 更新 `tool_fetch_current_gold_quote`、agent health check 和 research-run 的 quote 流程，保证 TradingView 不可用时返回明确失败而不是 fallback
- [ ] 1.3 补充 TradingView quote 成功/失败的单元测试，覆盖页面解析成功、页面结构变化、网络失败和不允许回退到旧源的场景

## 2. API 与前端来源一致化

- [ ] 2.1 更新 API forecast contract 的来源说明，确保 `data_source` 对外只标识 TradingView，不再出现 Gold API 运行时来源
- [ ] 2.2 更新前端 `forecastApi`、dashboard 及相关类型/常量，保证实时价格快照、来源标签和错误状态都按 TradingView-only 语义展示
- [ ] 2.3 补充前端类型检查与构建验证，确认没有残留的旧源文案或硬编码 fallback

## 3. 回归验证与清理

- [ ] 3.1 运行后端测试，验证 research-run、health check、quote provider 和 API 响应都只使用 TradingView 实时 quote
- [ ] 3.2 运行前端 `npm run typecheck` 与 `npm run build`，确认 dashboard 能正确展示 TradingView 来源与 unavailable 状态
- [ ] 3.3 复查代码与文档，移除与 Gold API runtime fallback 相关的残留说明，确保仓库内不会再把旧源描述成实时来源
