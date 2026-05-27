## ADDED Requirements

### Requirement: TradingView is the only runtime source for current XAUUSD quote
系统 SHALL 在需要 current/latest XAUUSD quote 时，唯一使用 TradingView 的 `https://www.tradingview.com/symbols/XAUUSD/` 页面数据；不得把 Gold API、旧候选 URL、缓存旧值或 mock 数据作为默认候选或自动回退来源。

#### Scenario: 获取实时报价
- **WHEN** workflow 请求 current/latest XAUUSD quote
- **THEN** 系统 MUST 请求 `https://www.tradingview.com/symbols/XAUUSD/` 并解析页面中可验证的实时价格、时间戳和来源标识

#### Scenario: TradingView 不可用
- **WHEN** TradingView 页面不可达、返回结构变化或解析失败
- **THEN** 系统 MUST 返回明确的失败或 unavailable 状态，不得切换到 Gold API 或其他历史/缓存来源冒充最新报价

### Requirement: Realtime quote output preserves source traceability
系统 SHALL 将 TradingView 解析出的实时 quote 作为结构化数据输出，并保留 `data_source` 与 `data_timestamp` 供 workflow、API 和 frontend 统一展示。

#### Scenario: Quote 解析成功
- **WHEN** TradingView 页面成功返回可验证的实时价格
- **THEN** 系统 MUST 输出 `CurrentQuote`，其中 `data_source` 反映 TradingView 来源，`data_timestamp` 反映实际抓取或页面更新时间

#### Scenario: 来源标签对外可见
- **WHEN** API 或前端展示当前报价
- **THEN** 系统 MUST 明确显示 TradingView 作为实时 quote 来源，不得展示 Gold API 作为运行时来源

### Requirement: Realtime quote failures are explicit and non-fabricated
系统 SHALL 在实时 quote 不可解析或不可用时显式失败，不得生成伪造价格、伪造来源或伪造时间戳填充页面。

#### Scenario: 页面结构变化导致解析失败
- **WHEN** TradingView 页面结构变化导致解析器无法提取价格字段
- **THEN** 系统 MUST 返回受控错误并停止继续分析依赖 current quote 的节点

#### Scenario: 网络失败导致不可用
- **WHEN** 网络超时、HTTP 错误或非预期响应导致无法读取 TradingView 页面
- **THEN** 系统 MUST 返回 unavailable 或结构化错误，不得退回到旧实时源冒充最新数据
