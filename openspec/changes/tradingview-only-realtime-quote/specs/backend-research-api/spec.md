## MODIFIED Requirements

### Requirement: API returns structured forecast contracts
系统 SHALL 使用 Pydantic models 定义 API 响应，不得只返回自由文本预测报告，并且实时 quote 字段必须反映 TradingView 的页面数据源。

#### Scenario: 预测响应包含必要字段
- **WHEN** API 返回 forecast
- **THEN** 响应 MUST 包含当前/latest 黄金价格、数据时间、数据来源、multi-agent 摘要、最终方向、建议买入点、止盈点、止损点、风险提示、置信度、当日操作建议、长期持有建议和建议持有周期

#### Scenario: 方向字段可被前端稳定映射
- **WHEN** API 返回最终方向
- **THEN** `direction` MUST 使用 `bullish`、`bearish` 或 `neutral` 之一

#### Scenario: 实时报价来源必须可追踪
- **WHEN** API 返回包含 current/latest XAUUSD quote 的 forecast
- **THEN** `data_source` MUST 明确标识 TradingView 的 `XAUUSD` 页面来源，且 API MUST NOT 将 Gold API 作为运行时来源对外展示

### Requirement: API errors are explicit and frontend consumable
系统 SHALL 返回清晰、稳定的错误结构，便于前端展示 loading、empty、error 和 success 状态。

#### Scenario: 创建研究运行不依赖手工 quote URL
- **WHEN** 调用方请求 `POST /api/v1/research-runs`
- **THEN** 系统 MUST 在未配置手工 current quote URL 的情况下，仍尝试通过内部 TradingView quote discovery tool 完成研究流程

#### Scenario: TradingView 实时查价失败
- **WHEN** 内部 TradingView quote discovery tool 无法获得有效实时金价
- **THEN** API MUST 返回明确的结构化错误，并记录 research run 失败状态，不得自动切换到 Gold API 或其他旧源
