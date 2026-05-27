## ADDED Requirements

### Requirement: Polymarket public pages are a structured sentiment source
系统 SHALL 能够从 `https://polymarket.com/zh` 及其公开可访问的市场页面采集与黄金相关的公开市场数据，并将其整理为结构化输入供 agent 分析。

#### Scenario: 采集到公开市场数据
- **WHEN** tool 节点访问 Polymarket 公开页面并发现与黄金相关的市场
- **THEN** 系统 MUST 返回结构化市场列表，至少包含标题、URL、概率或价格、流动性/成交量（如可用）、到期时间（如可用）和相关性标记

#### Scenario: 页面不可用或结构变化
- **WHEN** Polymarket 页面不可访问、内容缺失或无法解析
- **THEN** 系统 MUST 将该信号标记为 `unavailable`，并提供明确的失败原因

### Requirement: Polymarket analysis outputs must remain structured
系统 SHALL 将 Polymarket 相关市场信号整理为结构化分析结果，而不是仅返回自由文本。

#### Scenario: agent 分析黄金相关市场
- **WHEN** Polymarket agent 识别到与黄金相关的事件市场或宏观市场
- **THEN** 系统 MUST 输出 summary、direction、confidence 和风险提示，并说明其与黄金的关联

#### Scenario: 没有足够相关市场
- **WHEN** 当前没有足够相关的 Polymarket 市场可供判断
- **THEN** 系统 MUST 返回 `neutral` 或 `unavailable` 的结构化结果，并说明缺失原因

