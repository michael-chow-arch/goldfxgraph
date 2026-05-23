## Purpose

定义 GoldFXGraph 多 Agent LangGraph workflow 的节点职责、结构化输出和 research-only 约束，确保分析流程可解释、可测试且边界明确。

## Requirements

### Requirement: Workflow uses explicit LangGraph node responsibilities
系统 SHALL 使用 LangGraph 实现多 Agent 研究 workflow，并使用明确节点名区分 router、tool 和 agent 职责。

#### Scenario: Workflow 包含必需节点
- **WHEN** 研究 workflow 被构建
- **THEN** 图中 MUST 包含 `router_validate_request`、`tool_load_market_data`、`tool_fetch_current_gold_quote`、`tool_compute_indicators`、`agent_technical_analysis`、`agent_macro_analysis`、`agent_news_analysis`、`agent_risk_analysis`、`agent_forecast_planning`、`tool_persist_research_run`、`tool_persist_forecast` 和 `router_finalize_result`

#### Scenario: Tool 节点执行确定性工作
- **WHEN** workflow 执行 tool 节点
- **THEN** tool 节点 MUST 只执行加载数据、获取报价、计算指标或持久化等确定性职责

#### Scenario: Tool 节点执行自动查价
- **WHEN** workflow 执行 `tool_fetch_current_gold_quote`
- **THEN** 该节点 MUST 通过系统内置 quote discovery tool 获取并结构化 current quote，而不是要求用户必须配置手工 quote URL

#### Scenario: Agent 节点输出结构化摘要
- **WHEN** workflow 执行 agent 节点
- **THEN** agent 节点 MUST 输出结构化摘要、投票或风险说明，而不是只输出不可解析自由文本

#### Scenario: Agent 节点调用 OpenAI-compatible 模型
- **WHEN** workflow 执行技术、宏观、新闻或风险 agent 节点且 OpenAI-compatible 配置可用
- **THEN** agent 节点 MUST 优先调用 OpenAI-compatible 模型生成结构化摘要、投票和风险说明

### Requirement: Forecast planning produces structured forecast output
系统 SHALL 在最终预测规划节点生成结构化预测结果，并保留各 agent 的分析摘要与投票。

#### Scenario: 生成最终方向和交易研究字段
- **WHEN** `agent_forecast_planning` 汇总技术、宏观/新闻和风险分析
- **THEN** 输出 MUST 包含 `direction`、`entry_price`、`take_profit_price`、`stop_loss_price`、`holding_period`、`intraday_action`、`long_term_action`、`confidence_score` 和 `risk_notes`

#### Scenario: 保留 multi-agent 分析
- **WHEN** workflow 最终结果返回给 API
- **THEN** 结果 MUST 包含 `technical_summary`、`macro_summary`、`news_summary`、`risk_summary` 和 `agent_votes`

#### Scenario: 模型调用失败时保持结构化结果边界
- **WHEN** 某个 agent 的 OpenAI-compatible 调用失败或返回无效结构
- **THEN** 系统 MUST 返回受控错误或 deterministic fallback 结果，并保持最终 forecast contract 不变

### Requirement: Workflow remains research-only
系统 SHALL 将输出限定为研究和决策支持，不得触发自动交易、真实下单或券商集成。

#### Scenario: 预测结果包含免责声明
- **WHEN** workflow 返回 forecast
- **THEN** 结果 MUST 包含说明该输出仅用于研究、不是金融建议的 disclaimer

#### Scenario: 不执行交易动作
- **WHEN** workflow 生成 entry、take-profit 和 stop-loss 建议
- **THEN** 系统 MUST NOT 调用任何下单、交易执行或券商 API
