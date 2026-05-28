## ADDED Requirements

### Requirement: Workflow must include a Polymarket sentiment path
系统 SHALL 在市场情绪分析链路中增加 Polymarket 公开页面数据采集与分析节点，使 agent 可以基于公开市场概率判断对黄金的潜在影响。

#### Scenario: Workflow graph includes Polymarket nodes
- **WHEN** workflow graph is built
- **THEN** graph MUST include `tool_fetch_polymarket_inputs` and `agent_polymarket_analysis`

#### Scenario: Polymarket 信号不可用
- **WHEN** Polymarket 页面返回不可用、无法解析或无相关市场
- **THEN** workflow MUST 标记该信号为 `unavailable`，并继续执行后续市场情绪与 forecast planning 节点

## MODIFIED Requirements

### Requirement: Forecast planning must consume sentiment and feedback context
系统 SHALL 在最终 forecast planning 阶段结合技术、宏观、新闻、风险、情绪、另类数据、Polymarket 信号和历史反馈，输出结构化预测结果。

#### Scenario: 多源上下文可用
- **WHEN** 所有核心分析上下文均可用
- **THEN** `agent_forecast_planning` MUST 综合这些输入生成 direction、entry、take-profit、stop-loss、confidence 和 risk notes

#### Scenario: 部分上下文不可用
- **WHEN** 某些 sentiment、Polymarket 或 alt-data 信号不可用
- **THEN** `agent_forecast_planning` MUST 使用其余可用上下文完成预测，并显式标记缺失信号
