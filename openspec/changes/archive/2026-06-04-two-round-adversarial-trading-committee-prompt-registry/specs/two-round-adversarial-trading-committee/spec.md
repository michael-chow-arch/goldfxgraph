## ADDED Requirements

### Requirement: 系统必须先构建 evidence package 再进入交易委员会辩论
系统 SHALL 在所有 specialist agents 完成后，先汇总生成统一的 evidence package，再允许 bull / bear / chair / repair 相关 agents 进入委员会流程；specialist 输出不得直接进入最终 forecast 汇总。

#### Scenario: 所有 specialist 已完成
- **WHEN** technical、macro、news、sentiment、alternative data 和 risk 分析均已完成
- **THEN** 系统 MUST 构建 evidence package，且该 package MUST 包含每个 specialist 的 signal、confidence、key evidence、risk factors、invalidation conditions、important levels、data freshness 和 tool status

#### Scenario: 部分输入存在 degraded 状态
- **WHEN** 某些 specialist 或工具返回 degraded / unavailable
- **THEN** evidence package MUST 仍然生成，并显式记录 degraded source、缺失信号与其对委员会判断的影响

### Requirement: 系统必须执行两轮对抗式交易委员会辩论
系统 SHALL 采用固定的 two-round debate 拓扑执行委员会决策，且流程必须严格按依赖顺序运行，禁止无限轮次或自由聊天。

#### Scenario: Round 1 opening case 可以并行
- **WHEN** evidence package 已生成
- **THEN** `agent_bull_opening_case` 与 `agent_bear_opening_case` MUST 可以并行执行，并且双方都必须基于 evidence package 论证

#### Scenario: Round 2 rebuttal 需要等待双方 opening
- **WHEN** bull 和 bear opening case 都已完成
- **THEN** `agent_bull_rebuttal` 与 `agent_bear_rebuttal` MUST 仅能在此之后执行，并且必须逐点回应对方 opening case

#### Scenario: Final position 需要等待双方 rebuttal
- **WHEN** bull 和 bear rebuttal 都已完成
- **THEN** `agent_bull_final_position` 与 `agent_bear_final_position` MUST 仅能在此之后执行，并且必须说明是否仍坚持原观点、最终置信度与放弃条件

#### Scenario: Chair 需要等待双方 final position
- **WHEN** bull 和 bear final position 都已完成
- **THEN** `agent_trading_committee_chair` MUST 仅能在此之后执行，并输出最终仲裁结果而不是简单摘要

### Requirement: Bull 与 Bear opening case 必须基于 evidence package 论证
系统 SHALL 要求 bull / bear opening case 只引用 evidence package 中的证据，且必须给出与各自交易方向一致的入场区、失效条件、目标区和风险收益框架。

#### Scenario: Bull opening case
- **WHEN** `agent_bull_opening_case` 执行
- **THEN** 输出 MUST 包含 long entry zone、stop / invalidation、target zone、risk-reward、弱点承认以及对 evidence package 的引用

#### Scenario: Bear opening case
- **WHEN** `agent_bear_opening_case` 执行
- **THEN** 输出 MUST 包含 short entry zone、stop / invalidation、target zone、risk-reward、弱点承认以及对 evidence package 的引用

### Requirement: Rebuttal 与 final position 必须是有限、可追踪的结构化辩论
系统 SHALL 让 bull / bear rebuttal 逐点回应对方 opening case，并要求 final position 明确表述 stance、置信度变化、交易计划调整和放弃条件。

#### Scenario: Bull rebuttal
- **WHEN** `agent_bull_rebuttal` 执行
- **THEN** 输出 MUST 说明反驳了 bear opening 的哪些观点、承认了哪些观点、是否需要调整交易计划，以及置信度是上升还是下降

#### Scenario: Bear rebuttal
- **WHEN** `agent_bear_rebuttal` 执行
- **THEN** 输出 MUST 说明反驳了 bull opening 的哪些观点、承认了哪些观点、是否需要调整交易计划，以及置信度是上升还是下降

#### Scenario: Final position 可降级行动性
- **WHEN** 任一 final position 评估后发现交易条件不足
- **THEN** 该 final position MUST 允许从 `trade_candidate` 降级为 `prepare_only`、`observe_only` 或 `no_trade`

### Requirement: Trading Committee Chair 必须输出最终仲裁结论与最终交易计划
系统 SHALL 由 `agent_trading_committee_chair` 综合 evidence package、opening case、rebuttal 和 final position，输出最终 bias、actionability、winning side、adopted arguments、rejected arguments 和最终交易计划。

#### Scenario: bullish 结论
- **WHEN** chair 输出 `final_bias = bullish`
- **THEN** 结果 MUST 包含 `long_plan`，且 `long_plan` 至少包含 `entry_zone`、`stop_loss` 或 `invalidation_level`、`target_zone`、`risk_reward`、`conditions_to_enter` 和 `conditions_to_abort`

#### Scenario: bearish 结论
- **WHEN** chair 输出 `final_bias = bearish`
- **THEN** 结果 MUST 包含 `short_plan`，且 `short_plan` 至少包含 `entry_zone`、`stop_loss` 或 `invalidation_level`、`target_zone`、`risk_reward`、`conditions_to_enter` 和 `conditions_to_abort`

#### Scenario: range_bound 结论
- **WHEN** chair 输出 `final_bias = range_bound`
- **THEN** 结果 MUST 包含 `range_plan`，且 `range_plan` 至少包含 `upper_sell_zone`、`lower_buy_zone`、`upper_stop`、`lower_stop`、`midline_target`、`breakout_confirmation_level`、`breakdown_confirmation_level` 和 `range_invalidated_if`

#### Scenario: cautious 结论
- **WHEN** chair 输出 `final_bias = cautious`
- **THEN** 结果 MUST 包含 `wait_conditions`，并说明为什么当前不适合直接入场

### Requirement: Decision validator must enforce committee output rules without relying only on LLM judgement
系统 SHALL 使用规则节点校验最终委员会输出，至少检查 final_bias、actionability、confidence、计划字段存在性、价格逻辑、trade_candidate 阈值、degraded source 风险和风险收益约束。

#### Scenario: bullish 结果缺少 long_plan
- **WHEN** `final_bias = bullish` 但缺少 `long_plan`
- **THEN** `node_validate_committee_decision` MUST 判定结果无效

#### Scenario: bearish 结果缺少 short_plan
- **WHEN** `final_bias = bearish` 但缺少 `short_plan`
- **THEN** `node_validate_committee_decision` MUST 判定结果无效

#### Scenario: range_bound 结果缺少 range_plan
- **WHEN** `final_bias = range_bound` 但缺少 `range_plan`
- **THEN** `node_validate_committee_decision` MUST 判定结果无效

#### Scenario: cautious 结果缺少 wait_conditions
- **WHEN** `final_bias = cautious` 但缺少 `wait_conditions`
- **THEN** `node_validate_committee_decision` MUST 判定结果无效

#### Scenario: confidence 超出范围
- **WHEN** confidence 小于 0 或大于 1
- **THEN** `node_validate_committee_decision` MUST 判定结果无效

#### Scenario: 低置信度却被标记为 trade_candidate
- **WHEN** `actionability = trade_candidate` 且 confidence 低于合理阈值
- **THEN** `node_validate_committee_decision` MUST 判定结果无效或要求降级

#### Scenario: 风险收益比过低
- **WHEN** 交易计划的风险收益比明显不足以支持入场
- **THEN** `node_validate_committee_decision` MUST 阻止 `trade_candidate` 结论

### Requirement: Validation failure may trigger bounded repair and must gate persistence
系统 SHALL 在 validation 失败后最多调用 1 到 2 次 `agent_repair_committee_decision` 修复，且只有 validation 通过后才允许持久化最终 forecast。

#### Scenario: 首次 validation 失败但 repair 成功
- **WHEN** validator 发现可修复错误
- **THEN** workflow MAY 调用 `agent_repair_committee_decision` 重新生成受限修复结果，并再次执行 validator

#### Scenario: repair 次数超过上限
- **WHEN** validation 在修复后仍失败，且修复次数已达到上限
- **THEN** workflow MUST 标记委员会决策失败并不得执行 forecast 持久化

#### Scenario: validation 通过
- **WHEN** `node_validate_committee_decision` 判定结果有效
- **THEN** workflow MUST 允许 `node_persist_forecast` 执行
