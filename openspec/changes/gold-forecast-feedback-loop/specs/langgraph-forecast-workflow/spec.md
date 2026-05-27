## ADDED Requirements

### Requirement: Workflow 必须加载历史反馈并纳入 forecast planning
系统 SHALL 在 `agent_forecast_planning` 之前加载最近的 evaluation 反馈摘要，让后续 forecast 能基于历史命中情况与误差模式做出调整。

#### Scenario: 历史反馈存在
- **WHEN** 新一轮研究流程启动
- **THEN** 系统 MUST 读取最近的 evaluation 摘要、命中率和常见误差模式，并传递给 forecast planning

#### Scenario: 历史反馈不存在
- **WHEN** 数据库中没有可用反馈
- **THEN** 系统 MUST 继续执行 forecast planning，并使用空反馈上下文

### Requirement: Workflow must include sentiment and alt-data nodes
系统 SHALL 在现有技术、宏观、新闻和风险分析节点之外，增加情绪与另类数据分析节点，用于接入美国披萨指数等补充信号。

#### Scenario: Workflow 包含新增节点
- **WHEN** workflow graph is built
- **THEN** graph MUST include `tool_load_forecast_feedback_history`, `tool_fetch_market_sentiment_inputs`, `tool_fetch_alt_data_inputs`, `agent_market_sentiment_analysis` and `agent_alt_data_analysis`

#### Scenario: 节点返回结构化结果
- **WHEN** 新增的 tool 或 agent 节点执行成功
- **THEN** 系统 MUST 返回结构化 summary、vote、risk note 或 unavailable 状态，而不是仅返回自由文本

### Requirement: Forecast planning must consume sentiment and feedback context
系统 SHALL 在最终 forecast planning 阶段结合技术、宏观、新闻、风险、情绪、另类数据和历史反馈，输出结构化预测结果。

#### Scenario: 多源上下文可用
- **WHEN** 所有核心分析上下文均可用
- **THEN** `agent_forecast_planning` MUST 综合这些输入生成 direction、entry、take-profit、stop-loss、confidence 和 risk notes

#### Scenario: 部分上下文不可用
- **WHEN** 某些 sentiment 或 alt-data 信号不可用
- **THEN** `agent_forecast_planning` MUST 使用其余可用上下文完成预测，并显式标记缺失信号
