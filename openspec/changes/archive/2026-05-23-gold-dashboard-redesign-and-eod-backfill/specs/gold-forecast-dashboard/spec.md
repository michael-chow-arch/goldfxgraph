## ADDED Requirements

### Requirement: Dashboard uses a premium dark gold research cockpit layout
系统 SHALL 将黄金预测 Dashboard 设计为深色金融研究面板，使用高对比度的暗色背景、金色强调色和清晰的信息层级，让最新价格、方向、置信度与风险信息在首屏即可被快速扫读。

#### Scenario: Desktop layout emphasizes the core forecast first
- **WHEN** 用户在桌面端打开 Dashboard
- **THEN** 页面 MUST 先展示最新价格、方向和置信度的核心结论区，再展示 OHLC、交易研究字段、agent 摘要与风险信息

#### Scenario: Visual treatment matches the research context
- **WHEN** Dashboard 渲染 forecast 内容
- **THEN** 页面 MUST 使用深色背景、金色高亮和技术感字体风格，避免普通营销页或浅色默认后台风格

#### Scenario: Mobile layout preserves readability
- **WHEN** 用户在窄屏设备上打开 Dashboard
- **THEN** 页面 MUST 将核心结论、OHLC、交易研究字段、摘要和免责声明纵向堆叠，并保持文本可读与点击区域可访问
