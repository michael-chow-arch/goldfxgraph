## MODIFIED Requirements

### Requirement: Workflow uses explicit LangGraph node responsibilities
系统 SHALL 使用 LangGraph 实现多 Agent 研究 workflow，并使用明确节点名区分 router、tool 和 agent 职责。

#### Scenario: Tool 节点执行自动查价
- **WHEN** workflow 执行 `tool_fetch_current_gold_quote`
- **THEN** 该节点 MUST 通过系统内置 quote discovery tool 获取并结构化 current quote，而不是要求用户必须配置手工 quote URL

#### Scenario: Agent 节点调用 OpenAI-compatible 模型
- **WHEN** workflow 执行技术、宏观、新闻或风险 agent 节点且 OpenAI-compatible 配置可用
- **THEN** agent 节点 MUST 优先调用 OpenAI-compatible 模型生成结构化摘要、投票和风险说明

### Requirement: Forecast planning produces structured forecast output
系统 SHALL 在最终预测规划节点生成结构化预测结果，并保留各 agent 的分析摘要与投票。

#### Scenario: 模型调用失败时保持结构化结果边界
- **WHEN** 某个 agent 的 OpenAI-compatible 调用失败或返回无效结构
- **THEN** 系统 MUST 返回受控错误或 deterministic fallback 结果，并保持最终 forecast contract 不变
