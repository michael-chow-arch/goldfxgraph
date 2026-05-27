## ADDED Requirements

### Requirement: Daily backfill runs after the U.S. gold market close
系统 SHALL 在美国黄金市场收市后执行每日补数任务，并使用 `America/New_York` 时区计算触发窗口，确保在收市缓冲期之后再开始检查 CSV。

#### Scenario: Scheduled backfill starts at the close window
- **WHEN** 调度器在每日收市窗口触发补数任务
- **THEN** 系统 MUST 读取配置的 XAUUSD CSV，并计算最新已完成日线的日期

#### Scenario: No-op when CSV is already current
- **WHEN** CSV 最新日期已经覆盖到最新可补齐的 completed trading day
- **THEN** 系统 MUST 不修改文件内容，并返回明确的 no-op 状态

### Requirement: Backfill detects missing daily bars from the CSV date gap
系统 SHALL 比较 CSV 最新日期与应有的交易日序列，计算出缺失的 completed daily bars，并按日期顺序逐日补齐。

#### Scenario: Missing trading days are found
- **WHEN** CSV 最新日期早于最新可补齐交易日，且中间存在一个或多个缺失交易日
- **THEN** 系统 MUST 按时间顺序枚举缺失日期，并逐日尝试补数

#### Scenario: Gaps are not guessed silently
- **WHEN** 系统无法确认某个日期是否属于应补齐的交易日
- **THEN** 系统 MUST 将该日期保留为待确认状态，而不是直接写入推测值

### Requirement: Agent-assisted queries must be validated before persistence
系统 SHALL 通过 agent-assisted data discovery 获取候选黄金日线数据，但在写回 CSV 之前必须执行确定性校验，避免把无效或重复数据写入文件。

#### Scenario: Candidate bar passes validation
- **WHEN** agent 返回某个缺失日期的候选 OHLC 数据
- **THEN** 系统 MUST 校验日期、symbol、OHLC 范围、来源字段和连续性后才允许写回 CSV

#### Scenario: Candidate bar fails validation
- **WHEN** agent 返回的候选数据缺少必要字段、日期冲突或 OHLC 不合法
- **THEN** 系统 MUST 拒绝写入该条数据，并保留原始 CSV 不变

### Requirement: CSV updates are atomic and preserve provenance
系统 SHALL 以原子方式更新 CSV，并保留每条补入数据的来源与时间信息，避免部分写入或文件损坏。

#### Scenario: Atomic replacement succeeds
- **WHEN** 所有待补日期的数据都通过校验
- **THEN** 系统 MUST 先写入临时文件，再原子替换目标 CSV

#### Scenario: Partial write is interrupted
- **WHEN** 补数过程在写盘中断或失败
- **THEN** 系统 MUST 保持原 CSV 不被破坏，并返回受控失败状态
