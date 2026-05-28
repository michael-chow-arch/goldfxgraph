## ADDED Requirements

### Requirement: Workflow 必须包含市场情绪与另类数据分析能力
系统 SHALL 在 LangGraph workflow 中显式加入市场情绪与另类数据分析节点，用于补充技术、宏观、新闻和风险分析之外的信号。

#### Scenario: Workflow 构建成功
- **WHEN** workflow 被初始化
- **THEN** 图中 MUST 包含 `tool_fetch_market_sentiment_inputs`, `agent_market_sentiment_analysis`, `tool_fetch_alt_data_inputs` 和 `agent_alt_data_analysis`

#### Scenario: 节点职责清晰
- **WHEN** workflow 执行上述节点
- **THEN** tool 节点 MUST 只负责采集结构化输入，agent 节点 MUST 只负责解释、归纳和给出结构化结论

### Requirement: 市场情绪与另类数据必须支持结构化输出
系统 SHALL 将市场情绪、美国披萨指数等另类数据整理为结构化分析结果，并输出可供 forecast planning 使用的摘要、投票和风险信息。

#### Scenario: 采集到披萨指数数据
- **WHEN** tool 节点成功获取美国披萨指数或其他另类数据
- **THEN** 系统 MUST 将数据整理为结构化字段，并交给 agent 进行分析

#### Scenario: 另类数据源不可用
- **WHEN** 某个另类数据源不可用或返回无效结果
- **THEN** 系统 MUST 将该信号标记为 `unavailable`，并继续使用其他可用信号完成分析

#### Scenario: agent 输出预测可用摘要
- **WHEN** market sentiment 或 alt-data agent 完成分析
- **THEN** 系统 MUST 输出结构化 summary、confidence 或 vote 信息，而不是只有自由文本
