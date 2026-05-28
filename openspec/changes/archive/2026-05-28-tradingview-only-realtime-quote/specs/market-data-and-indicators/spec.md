## MODIFIED Requirements

### Requirement: Current gold quote is fetched from TradingView page data only
系统 SHALL 在需要 current/latest 黄金价格时，通过 TradingView 的 `XAUUSD` 页面抓取实时报价，并将其与 completed daily bars 区分开；系统不得使用 Gold API、旧候选 URL、缓存旧值或 mock 数据作为实时报价来源。

#### Scenario: TradingView quote discovered
- **WHEN** workflow 请求 current/latest XAUUSD quote
- **THEN** 系统 MUST 从 `https://www.tradingview.com/symbols/XAUUSD/` 解析实时价格、数据时间戳和来源标识，并输出到 `CurrentQuote`

#### Scenario: TradingView quote unavailable
- **WHEN** TradingView 页面不可达、返回结构变化或解析失败
- **THEN** 系统 MUST 返回明确错误或受控 unavailable 状态，不得使用 Gold API、历史 completed daily bar、缓存值或 mock 数据冒充 current quote

#### Scenario: Completed daily bars stay separate
- **WHEN** workflow loads historical completed daily bars
- **THEN** 系统 MUST 继续将 daily bars 作为独立数据集处理，不得把 TradingView current quote 直接写回为历史 completed bar
