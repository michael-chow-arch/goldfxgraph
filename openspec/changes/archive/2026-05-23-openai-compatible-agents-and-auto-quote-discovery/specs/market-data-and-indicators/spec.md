## MODIFIED Requirements

### Requirement: Current gold quote is fetched separately from daily bars
系统 SHALL 在需要 current/latest 黄金价格时，通过系统内置的候选数据源发现与查询流程获取报价，并记录数据来源和时间，不得把 completed daily bar 与 current quote 混为一谈。

#### Scenario: Quote discovery 成功
- **WHEN** workflow 请求 current/latest XAUUSD quote 且某个候选 source 返回有效报价
- **THEN** 系统 MUST 记录 `current_price`、`data_source` 和 `data_timestamp`

#### Scenario: 未提供手工 quote URL
- **WHEN** 用户未配置显式 quote URL
- **THEN** 系统 MUST 仍尝试使用内置 quote discovery 流程获取实时价格

#### Scenario: 所有候选 source 均失败
- **WHEN** 系统无法从任何候选 source 获得有效 current quote
- **THEN** 系统 MUST 返回明确错误或受控失败状态，不得用 mock 数据冒充真实报价
