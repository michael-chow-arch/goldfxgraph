## ADDED Requirements

### Requirement: Forecast planning emits fixed-window direction intervals
系统 SHALL 在 forecast planning 阶段输出固定时间窗口的方向区间，而不是只返回单一总体方向描述。

#### Scenario: Planning produces structured window outputs
- **WHEN** `agent_forecast_planning` 接收到技术、宏观、新闻、风险和情绪分析结果
- **THEN** 系统 MUST 生成按窗口分组的方向输出，例如 `0-3天`、`3-5天`、`6-15天` 和 `15天后`

#### Scenario: Each window includes direction and rationale
- **WHEN** 系统输出某个时间窗口的判断
- **THEN** 该窗口 MUST 包含 `direction`、`strength`、`confidence` 和简短 `reason`

#### Scenario: Optional extra observation window is allowed
- **WHEN** agent 认为标准窗口之外还需要额外说明
- **THEN** 系统 MAY 附加一个补充观察窗口，但不得替代固定窗口集合

### Requirement: Existing analysis nodes remain in the current workflow order
系统 SHALL 保持现有技术分析、宏观分析、新闻分析、风险分析和相关辅助节点的职责边界不变，仅调整最终 forecast 的组织方式。

#### Scenario: Workflow still runs the same core analysis chain
- **WHEN** 统一研究循环执行 workflow
- **THEN** 系统 MUST 继续完成技术、宏观、新闻和风险分析节点，再进入 forecast planning

#### Scenario: Workflow continues to produce structured reasoning
- **WHEN** workflow 输出 forecast
- **THEN** 系统 MUST 保留现有分析原因列表与 risk notes，而不是退化成纯自由文本
