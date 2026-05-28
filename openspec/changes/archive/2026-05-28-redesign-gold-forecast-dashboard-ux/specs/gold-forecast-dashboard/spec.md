## MODIFIED Requirements

### Requirement: Dashboard displays structured forecast fields clearly
系统 SHALL 清晰展示黄金预测结构化字段，并将研究结论、交易字段、证据与风险分区呈现，以便用户在首屏快速识别核心方向与关键价格。

#### Scenario: 展示核心价格与方向
- **WHEN** API 返回 forecast
- **THEN** Dashboard MUST 在首屏优先展示 current/latest XAUUSD price、direction、confidence score、data timestamp、data source 和最新执行信息，并使核心结论具备明显的视觉优先级

#### Scenario: 展示交易研究字段
- **WHEN** API 返回 entry、take-profit、stop-loss 和 holding advice
- **THEN** Dashboard MUST 清晰展示建议买入点、止盈点、止损点、风险回报比、当日操作建议、长期持有建议和建议持有周期，并保持这些字段与解释文本视觉分离

#### Scenario: 展示 multi-agent 摘要和风险
- **WHEN** API 返回 agent summaries 和 risk notes
- **THEN** Dashboard MUST 将技术分析、宏观分析、新闻分析、市场情绪、风险分析、多 Agent 投票、关键风险与研究免责声明分区展示，并保持每个分区具备明确标题与视觉层级

### Requirement: Dashboard has professional states and layout
系统 SHALL 提供适合研究工作的 Dashboard 布局，并包含 loading、error、empty 和 success 状态，且这些状态必须在视觉上与正常结果区清晰区分。

#### Scenario: API 请求中
- **WHEN** Dashboard 正在请求 forecast
- **THEN** 页面 MUST 显示 loading 状态、骨架或占位提示，并避免展示误导性的已完成研究结果

#### Scenario: API 请求失败
- **WHEN** forecast API 返回错误或不可访问
- **THEN** 页面 MUST 显示可读错误信息、恢复指引或重试入口，并保持布局稳定不跳变

#### Scenario: 没有预测结果
- **WHEN** API 表示尚无 forecast
- **THEN** 页面 MUST 显示 empty 状态，并引导用户等待研究运行或查看最新数据状态

#### Scenario: 响应式可读性
- **WHEN** 用户在桌面、平板或移动设备上查看 Dashboard
- **THEN** 页面 MUST 保持核心结论、交易字段、chart、摘要、风险提示与历史区在对应断点下可读且不发生信息丢失

### Requirement: Dashboard uses a premium dark gold research cockpit layout
系统 SHALL 将黄金预测 Dashboard 设计为深色金融研究面板，使用高对比度暗色背景、受控的金色强调与清晰的视觉层级，让最新价格、方向、置信度、K 线图与风险信息形成一个专业、克制且高级的研究 cockpit。

#### Scenario: Desktop layout emphasizes the core forecast first
- **WHEN** 用户在桌面端打开 Dashboard
- **THEN** 页面 MUST 优先展示核心结论区与主要交易字段，再展示 K 线图、摘要、风险提示和历史表现，避免所有模块并列争抢焦点

#### Scenario: Visual treatment matches the research context
- **WHEN** Dashboard 渲染 forecast 内容
- **THEN** 页面 MUST 使用统一的深色背景、细边框、层次化阴影、受控高亮和技术感字体风格，避免普通营销页或浅色默认后台风格

#### Scenario: Mobile layout preserves readability
- **WHEN** 用户在窄屏设备上打开 Dashboard
- **THEN** 页面 MUST 将核心结论、K 线图、交易字段、摘要、风险和免责声明纵向堆叠，并保证关键数值和标签仍可快速识别
