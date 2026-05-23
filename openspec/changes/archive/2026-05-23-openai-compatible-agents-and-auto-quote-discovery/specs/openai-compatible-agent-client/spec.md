## ADDED Requirements

### Requirement: Workflow agents support OpenAI-compatible model invocation
系统 SHALL 提供一个可复用的 OpenAI-compatible agent client，供技术、宏观、新闻和风险 agent 节点直接调用结构化模型分析能力。

#### Scenario: OpenAI-compatible configuration is present
- **WHEN** 后端已配置 `OPENAI_API_KEY` 或 `GOLDFXGRAPH_OPENAI_*` 所需字段
- **THEN** agent client MUST 能使用配置的 `base_url`、`model` 和 `api_key` 调用模型并返回结构化结果

#### Scenario: Model returns invalid structured payload
- **WHEN** OpenAI-compatible 模型返回非 JSON 或字段不符合约定
- **THEN** 系统 MUST 返回受控错误或 fallback 结果，不得把原始异常和 secret 暴露给 API 响应
