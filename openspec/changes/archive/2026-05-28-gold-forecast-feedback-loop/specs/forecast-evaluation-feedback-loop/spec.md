## ADDED Requirements

### Requirement: 每日收盘后自动评估当日 forecast
系统 SHALL 在美国市场收盘后的固定缓冲窗口自动运行每日评估任务，仅评估当日存在的 forecast 记录，并使用 `America/New_York` 时区计算触发时间。

#### Scenario: 收盘后存在当日 forecast
- **WHEN** 调度器在收盘后缓冲窗口触发评估任务，且数据库中存在当日 forecast
- **THEN** 系统 MUST 读取这些 forecast 并生成结构化 evaluation 结果

#### Scenario: 当日没有 forecast
- **WHEN** 调度器触发评估任务但当日没有任何 forecast
- **THEN** 系统 MUST 返回明确的 `skipped` 或 `no-op` 状态，并保留跳过原因

### Requirement: 评估结果必须量化 forecast 的实际表现
系统 SHALL 为每条被评估的 forecast 计算可复现的表现指标，包括是否触及 `take_profit_price` / `stop_loss_price`、方向命中、实际收益点数和评估结论。

#### Scenario: bullish forecast 命中 take-profit
- **WHEN** 某条 bullish forecast 的后续价格触及 `take_profit_price`
- **THEN** 系统 MUST 记录正向收益点数、命中结论和对应的 evaluation 结论

#### Scenario: bullish forecast 同时触及 take-profit 和 stop-loss
- **WHEN** 同一根 bar 同时触及 `take_profit_price` 与 `stop_loss_price`
- **THEN** 系统 MUST 使用保守且固定的判定规则生成 evaluation，不得随机选择结果

#### Scenario: 未触发止盈止损
- **WHEN** forecast 覆盖的评估窗口内未触发 `take_profit_price` 或 `stop_loss_price`
- **THEN** 系统 MUST 使用收盘价或约定的窗口结算价计算最终收益点数，并记录该结算口径

### Requirement: 评估结论必须作为后续 forecast 的反馈上下文
系统 SHALL 将历史 evaluation 的摘要、命中情况和常见误差模式保存为可查询反馈，用于后续 forecast planning 阶段作为结构化上下文。

#### Scenario: 后续 forecast 读取反馈
- **WHEN** 新一轮 research run 开始并进入 forecast planning
- **THEN** 系统 MUST 能读取最近的 evaluation 摘要作为输入上下文

#### Scenario: 反馈不可用时降级
- **WHEN** 历史 evaluation 暂不可用或为空
- **THEN** 系统 MUST 继续生成 forecast，并标记反馈上下文为空或不可用，而不是阻塞主流程

