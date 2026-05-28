## MODIFIED Requirements

### Requirement: Dashboard displays structured forecast fields clearly
系统 SHALL 清晰展示黄金预测结构化字段，并将研究解释与交易研究字段分区呈现，且当前/latest XAUUSD 价格来源必须明确显示为 TradingView。

#### Scenario: 展示核心价格与方向
- **WHEN** API 返回 forecast
- **THEN** Dashboard MUST 展示 current/latest XAUUSD price、data timestamp、data source、daily open/high/low/close、direction 和 confidence score，并将当前报价来源明确标识为 TradingView

#### Scenario: 展示交易研究字段
- **WHEN** API 返回 entry、take-profit、stop-loss 和 holding advice
- **THEN** Dashboard MUST 清晰展示建议买入点、止盈点、止损点、当日操作建议、长期持有建议和建议持有周期

#### Scenario: 展示 multi-agent 摘要和风险
- **WHEN** API 返回 agent summaries 和 risk notes
- **THEN** Dashboard MUST 展示技术分析、宏观分析、新闻分析、风险分析、多 Agent 投票、关键风险和研究免责声明

#### Scenario: 不展示旧实时源名称
- **WHEN** Dashboard 渲染 current/latest XAUUSD quote
- **THEN** 页面 MUST 不得将 Gold API、旧候选 URL 或任何历史回退源显示为运行时实时来源
