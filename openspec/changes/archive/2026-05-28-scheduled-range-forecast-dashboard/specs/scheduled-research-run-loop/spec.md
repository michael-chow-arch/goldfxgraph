## ADDED Requirements

### Requirement: Unified scheduler executes the research pipeline every 15 minutes
系统 SHALL 以固定 15 分钟周期执行统一的黄金研究循环，并在每次周期内按顺序完成最新黄金数据获取、当日最新黄金数据更新、多智能体日线分析和结果持久化。

#### Scenario: Scheduler tick starts a full research cycle
- **WHEN** 调度器到达下一次 15 分钟执行点
- **THEN** 系统 MUST 依次执行最新黄金数据获取、当日最新黄金数据更新、多智能体分析和持久化，并更新最近一次执行时间

#### Scenario: Research cycle records its current stage
- **WHEN** 统一研究循环正在执行
- **THEN** 系统 MUST 对外暴露当前阶段，例如 `fetch_market_data`、`update_latest_daily_bar`、`run_agent_analysis` 和 `persist_result`

### Requirement: Scheduler does not overlap active runs
系统 SHALL 保证同一时刻只有一个统一研究循环处于运行中，避免并发的重复写入和状态撕裂。

#### Scenario: A new tick arrives while a run is active
- **WHEN** 上一轮统一研究循环尚未完成，而新的 15 分钟 tick 到达
- **THEN** 系统 MUST 不启动第二个并行循环，并保留当前运行状态供前端查询

#### Scenario: Active run completes before the next tick
- **WHEN** 当前统一研究循环在下一次 tick 之前完成
- **THEN** 系统 MUST 允许下一次 tick 正常启动新的循环

### Requirement: Scheduler surfaces per-agent execution status
系统 SHALL 在统一研究循环执行期间暴露每个 agent 的执行状态，以便前端展示当前正在执行的分析步骤。

#### Scenario: An agent is running
- **WHEN** 多智能体分析中的某个 agent 正在执行
- **THEN** 系统 MUST 在状态输出中标记该 agent 的状态为 `running`，并保持其他 agent 的状态可见

#### Scenario: Scheduler finishes successfully
- **WHEN** 统一研究循环完成
- **THEN** 系统 MUST 返回最近一次执行时间、完成时间、最终状态和所有 agent 的最终状态
