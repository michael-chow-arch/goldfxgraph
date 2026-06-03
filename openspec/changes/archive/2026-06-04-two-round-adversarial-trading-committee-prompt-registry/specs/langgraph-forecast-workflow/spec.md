## REMOVED Requirements

### Requirement: Forecast planning must consume sentiment and feedback context
**Reason**: 现有单轮 forecast planning 已被 Two-Round Adversarial Trading Committee 的仲裁式最终决策层替代，最终 forecast 不再由 `agent_forecast_planning` 直接汇总生成。

**Migration**: 使用 evidence package、bull / bear opening case、rebuttal、final position 和 chair arbitration 生成最终 forecast；如需历史反馈，只能作为 committee 参考输入或风险上下文，而不能再作为单独的最终聚合节点。

## ADDED Requirements

### Requirement: Workflow must execute specialist analysis before building the committee evidence package
系统 SHALL 在生成 evidence package 之前，先完成 technical、macro、news、sentiment、alternative data 和 risk specialist analysis，并确保 specialist 输出只进入 evidence package 和委员会辩论，不直接进入最终 forecast 汇总。

#### Scenario: workflow graph 被构建
- **WHEN** workflow graph 初始化
- **THEN** graph MUST 包含 `node_build_evidence_package`、`agent_bull_opening_case`、`agent_bear_opening_case`、`agent_bull_rebuttal`、`agent_bear_rebuttal`、`agent_bull_final_position`、`agent_bear_final_position`、`agent_trading_committee_chair`、`node_validate_committee_decision`、`agent_repair_committee_decision` 和 `node_persist_forecast`

#### Scenario: specialist 全部完成后才可进入委员会
- **WHEN** specialist analysis 尚未全部完成
- **THEN** 系统 MUST NOT 构建 evidence package 或进入 committee debate

### Requirement: Workflow must gate persistence on committee validation success
系统 SHALL 在 `node_validate_committee_decision` 通过后才允许 `node_persist_forecast` 执行；如果 validation 失败，则 workflow 只能进入有限 repair 或失败路径，不能直接持久化最终 forecast。

#### Scenario: validation 通过
- **WHEN** committee decision 通过规则校验
- **THEN** workflow MUST 进入 `node_persist_forecast`

#### Scenario: validation 失败
- **WHEN** committee decision 未通过规则校验
- **THEN** workflow MUST 进入 repair 路径或失败路径，且不得直接 persist final forecast
