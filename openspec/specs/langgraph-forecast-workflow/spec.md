## ADDED Requirements

### Requirement: Workflow performs market data freshness preflight before forecast generation
系统 SHALL 在生成 forecast 之前先校验 completed daily bars 是否已经追平最新完成交易日；若未追平，系统必须先执行补齐检查，补齐失败则拒绝继续生成预测。

#### Scenario: Freshness gap is detected before workflow starts
- **WHEN** `research-run` 或 API 触发 workflow，且数据库最新 completed daily bar 早于当前最新完成交易日
- **THEN** 系统 MUST 先执行补齐流程，并且只有在补齐成功后才允许 workflow 继续执行

#### Scenario: Freshness gap cannot be repaired
- **WHEN** workflow 发现 completed daily bars 未追平，且 TradingView 补齐失败
- **THEN** 系统 MUST 返回受控错误，不得继续执行技术分析、宏观分析、新闻分析或 forecast planning

#### Scenario: Daily bars are current
- **WHEN** 数据库 latest completed daily bar 已经追平当前最新完成交易日
- **THEN** 系统 MUST 继续执行既有的 market data load、indicator compute 和 agent 分析流程
