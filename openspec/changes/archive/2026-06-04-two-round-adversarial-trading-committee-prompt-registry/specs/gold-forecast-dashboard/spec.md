## ADDED Requirements

### Requirement: Dashboard must surface Trading Committee evidence, debate and chair decision
系统 SHALL 在不破坏现有主结论布局的前提下，新增 Evidence Package Summary、Trading Committee Debate、Committee Chair Decision、Validation Status 和 Prompt Version Metadata 展示区域。

#### Scenario: 显示 evidence package
- **WHEN** API 返回 evidence package
- **THEN** Dashboard MUST 展示各 specialist 的 signal、confidence、key evidence、risk flags、invalidations 和 data freshness

#### Scenario: 显示 debate rounds
- **WHEN** API 返回 opening case、rebuttal 和 final position
- **THEN** Dashboard MUST 将 bull / bear 的各轮内容分开展示，且不把全部 reasoning 压成单一长文本

#### Scenario: 显示 chair decision
- **WHEN** API 返回 chair decision
- **THEN** Dashboard MUST 居中突出 final_bias、winning_side、actionability、confidence、adopted arguments、rejected arguments 和 final trade plan

#### Scenario: 显示 validation 与 prompt metadata
- **WHEN** API 返回 validation status 与 prompt version metadata
- **THEN** Dashboard MUST 在 Research Metadata 或类似区域展示 decision valid / repaired / failed，以及 prompt_key / prompt_version

### Requirement: Dashboard must render final bias specific plans and preserve research-only disclaimer
系统 SHALL 根据 final_bias 展示 long_plan、short_plan、range_plan 或 wait_conditions，并继续明确展示 research-only / not financial advice 声明。

#### Scenario: bullish 结果
- **WHEN** final_bias 为 bullish
- **THEN** Dashboard MUST 展示 long_plan 的 entry_zone、stop_loss / invalidation_level、target_zone、risk_reward、conditions_to_enter 和 conditions_to_abort

#### Scenario: bearish 结果
- **WHEN** final_bias 为 bearish
- **THEN** Dashboard MUST 展示 short_plan 的 entry_zone、stop_loss / invalidation_level、target_zone、risk_reward、conditions_to_enter 和 conditions_to_abort

#### Scenario: range_bound 结果
- **WHEN** final_bias 为 range_bound
- **THEN** Dashboard MUST 展示 range_plan 的 upper_sell_zone、lower_buy_zone、upper_stop、lower_stop、midline_target、breakout_confirmation_level、breakdown_confirmation_level 和 range_invalidated_if

#### Scenario: cautious 结果
- **WHEN** final_bias 为 cautious
- **THEN** Dashboard MUST 展示 wait_conditions，而不是强制展示入场点

### Requirement: Dashboard must expose graph execution trace for committee nodes
系统 SHALL 在 execution trace 中展示新增 committee 节点的执行状态，包括 completed、running、failed、degraded 和 pending。

#### Scenario: committee 节点执行中
- **WHEN** 任一 committee 节点正在执行
- **THEN** Dashboard MUST 在 graph trace 中显示该节点为 running，并保留其前置依赖状态

#### Scenario: validation 失败后进入 repair
- **WHEN** validator 失败且 repair 被触发
- **THEN** Dashboard MUST 显示 validation status 的 repaired / failed 过程，而不是仅展示最终结果
