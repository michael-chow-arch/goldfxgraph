## MODIFIED Requirements

### Requirement: Daily backfill runs after the U.S. gold market close and before service startup
系统 SHALL 在美国黄金市场收市后执行每日补数任务，并在服务启动前先补齐数据库中的 completed daily bars；系统必须使用 `America/New_York` 时区计算触发窗口，并确保补齐完成后才允许服务进入可用状态。

#### Scenario: Startup begins with missing daily bars
- **WHEN** 服务启动时发现数据库最新 completed daily bar 早于当前最新完成交易日
- **THEN** 系统 MUST 先执行补齐流程，并且只有在补齐成功后才允许启动继续

#### Scenario: Scheduled backfill starts at the close window
- **WHEN** 调度器在每日收市窗口触发补数任务
- **THEN** 系统 MUST 读取数据库中最新 completed daily bar，并计算最新已完成交易日

#### Scenario: No-op when database is already current
- **WHEN** 数据库最新 completed daily bar 已经覆盖到当前最新可补齐的 completed trading day
- **THEN** 系统 MUST 不修改数据库内容，并返回明确的 no-op 状态

### Requirement: Backfill detects missing daily bars from the database gap
系统 SHALL 比较数据库最新 completed daily bar 与应有的交易日序列，计算出缺失的 completed daily bars，并按日期顺序逐日补齐。

#### Scenario: Missing trading days are found
- **WHEN** 数据库最新日期早于最新可补齐交易日，且中间存在一个或多个缺失交易日
- **THEN** 系统 MUST 按时间顺序枚举缺失日期，并逐日尝试从 TradingView 补齐

#### Scenario: Gaps are not guessed silently
- **WHEN** 系统无法确认某个日期是否属于应补齐的交易日，或者 TradingView 未返回该日期的合法 completed daily bar
- **THEN** 系统 MUST 将该日期保留为待确认状态，并返回受控失败，而不是直接写入推测值

### Requirement: TradingView candidate bars must be validated before persistence
系统 SHALL 通过 TradingView 历史日线获取候选黄金日线数据，但在写入数据库之前必须执行确定性校验，避免把无效、重复或未完成的日线写入数据库。

#### Scenario: Candidate bar passes validation
- **WHEN** TradingView 返回某个缺失日期的候选 OHLC 数据
- **THEN** 系统 MUST 校验日期、symbol、OHLC 范围、来源字段和连续性后才允许写入数据库

#### Scenario: Candidate bar fails validation
- **WHEN** TradingView 返回的候选数据缺少必要字段、日期冲突、OHLC 不合法，或者看起来像未完成交易日
- **THEN** 系统 MUST 拒绝写入该条数据，并让补齐流程返回受控失败状态

### Requirement: Database updates are atomic and preserve provenance
系统 SHALL 以原子方式更新数据库中的 completed daily bars，并保留每条补入数据的来源与时间信息，避免部分写入或状态不一致。

#### Scenario: Atomic replacement succeeds
- **WHEN** 所有待补日期的数据都通过校验
- **THEN** 系统 MUST 使用幂等 upsert 写入数据库，并保留来源与更新时间

#### Scenario: Partial write is interrupted
- **WHEN** 补数过程在写入中断或失败
- **THEN** 系统 MUST 保持数据库中的已存在记录不被破坏，并返回受控失败状态
