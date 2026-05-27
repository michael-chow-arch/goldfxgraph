## Purpose

定义 GoldFXGraph 第一版黄金预测 Dashboard 的前端行为、数据来源与展示约束，确保页面基于真实 API 数据清晰呈现研究结果。
## Requirements
### Requirement: Vue dashboard fetches forecast from FastAPI
系统 SHALL 在 `apps/web/` 新增 Vue 3 + TypeScript + Vite + Tailwind CSS 前端，并通过 typed service 从 FastAPI 获取预测结果。

#### Scenario: Dashboard 加载最新预测
- **WHEN** 用户打开黄金预测 Dashboard
- **THEN** 前端 MUST 通过 `apps/web/src/services/forecastApi.ts` 调用 `GET /api/v1/forecast/latest`

#### Scenario: API base URL 来自环境变量
- **WHEN** 前端构建或运行
- **THEN** API base URL MUST 从 `VITE_API_BASE_URL` 读取，不得在 Vue 页面中硬编码后端地址

#### Scenario: 不硬编码预测假数据
- **WHEN** Dashboard 展示 forecast
- **THEN** 页面 MUST 使用 API 返回数据或明确的 loading/error/empty 状态，不得在生产页面中写死假预测数据

### Requirement: Dashboard displays structured forecast fields clearly
系统 SHALL 清晰展示黄金预测结构化字段，并将研究解释与交易研究字段分区呈现。

#### Scenario: 展示核心价格与方向
- **WHEN** API 返回 forecast
- **THEN** Dashboard MUST 展示 current/latest XAUUSD price、data timestamp、data source、daily open/high/low/close、direction 和 confidence score

#### Scenario: 展示交易研究字段
- **WHEN** API 返回 entry、take-profit、stop-loss 和 holding advice
- **THEN** Dashboard MUST 清晰展示建议买入点、止盈点、止损点、当日操作建议、长期持有建议和建议持有周期

#### Scenario: 展示 multi-agent 摘要和风险
- **WHEN** API 返回 agent summaries 和 risk notes
- **THEN** Dashboard MUST 展示技术分析、宏观分析、新闻分析、风险分析、多 Agent 投票、关键风险和研究免责声明

### Requirement: Dashboard has professional states and layout
系统 SHALL 提供适合研究工作的 Dashboard 布局，并包含 loading、error、empty 和 success 状态。

#### Scenario: API 请求中
- **WHEN** Dashboard 正在请求 forecast
- **THEN** 页面 MUST 显示 loading 状态且不显示误导性预测

#### Scenario: API 请求失败
- **WHEN** forecast API 返回错误或不可访问
- **THEN** 页面 MUST 显示可读错误信息和重试入口

#### Scenario: 没有预测结果
- **WHEN** API 表示尚无 forecast
- **THEN** 页面 MUST 显示 empty 状态，引导用户触发或等待研究运行

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

