## MODIFIED Requirements

### Requirement: Vue dashboard fetches forecast from FastAPI
系统 SHALL 在 `apps/web/` 新增 Vue 3 + TypeScript + Vite + Tailwind CSS 前端，并通过 typed service 从 FastAPI 获取最新预测结果与统一调度状态。

#### Scenario: Dashboard 加载最新预测
- **WHEN** 用户打开黄金预测 Dashboard
- **THEN** 前端 MUST 通过 `apps/web/src/services/forecastApi.ts` 调用 `GET /api/v1/forecast/latest`

#### Scenario: Dashboard 加载最新调度状态
- **WHEN** 用户打开黄金预测 Dashboard
- **THEN** 前端 MUST 通过 `apps/web/src/services/forecastApi.ts` 调用 `GET /api/v1/research-status/latest`

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
- **THEN** Dashboard MUST 在首屏展示 current/latest XAUUSD price、data timestamp、data source、daily open/high/low/close、总体方向和 confidence score

#### Scenario: 展示时间窗口方向区间
- **WHEN** API 返回固定时间窗口方向区间
- **THEN** Dashboard MUST 清晰展示各时间窗口的看多、看空或震荡判断，以及对应的强度和理由

#### Scenario: 展示交易研究字段
- **WHEN** API 返回 entry、take-profit、stop-loss 和 holding advice
- **THEN** Dashboard MUST 清晰展示建议买入点、止盈点、止损点、当日操作建议、长期持有建议和建议持有周期

#### Scenario: 展示 multi-agent 摘要和风险
- **WHEN** API 返回 agent summaries 和 risk notes
- **THEN** Dashboard MUST 展示技术分析、宏观分析、新闻分析、风险分析、多 Agent 投票、关键风险和研究免责声明

### Requirement: Dashboard has professional states and layout
系统 SHALL 提供适合研究工作的 Dashboard 布局，并包含 loading、error、empty、running 和 success 状态。

#### Scenario: API 请求中
- **WHEN** Dashboard 正在请求 forecast 或调度状态
- **THEN** 页面 MUST 显示 loading 状态且不显示误导性预测

#### Scenario: 调度正在运行
- **WHEN** 统一研究循环正在执行
- **THEN** 页面 MUST 显示最新执行时间、当前阶段和各 agent 状态

#### Scenario: API 请求失败
- **WHEN** forecast API 或调度状态 API 返回错误或不可访问
- **THEN** 页面 MUST 显示可读错误信息和重试入口

#### Scenario: 没有预测结果
- **WHEN** API 表示尚无 forecast
- **THEN** 页面 MUST 显示 empty 状态，引导用户等待研究运行

### Requirement: Dashboard uses a premium dark gold research cockpit layout
系统 SHALL 将黄金预测 Dashboard 设计为深色金融研究面板，使用高对比度的暗色背景、金色强调色和清晰的信息层级，让最新价格、方向、置信度与风险信息在首屏即可被快速扫读。

#### Scenario: Desktop layout emphasizes the core forecast first
- **WHEN** 用户在桌面端打开 Dashboard
- **THEN** 页面 MUST 先展示最新价格、方向区间和运行状态的核心结论区，再展示 OHLC、交易研究字段、agent 摘要与风险信息

#### Scenario: Visual treatment matches the research context
- **WHEN** Dashboard 渲染 forecast 内容
- **THEN** 页面 MUST 使用深色背景、金色高亮和技术感字体风格，避免普通营销页或浅色默认后台风格

#### Scenario: Mobile layout preserves readability
- **WHEN** 用户在窄屏设备上打开 Dashboard
- **THEN** 页面 MUST 将核心结论、OHLC、交易研究字段、摘要和免责声明纵向堆叠，并保持文本可读与点击区域可访问

## ADDED Requirements

### Requirement: Dashboard keeps the analysis list, candlestick chart, and news/sentiment sections unchanged
系统 SHALL 保持现有多 agent 分析原因列表、K 线图和最新市场新闻与情绪模块的功能和展示边界不变。

#### Scenario: Analysis reasons remain visible
- **WHEN** Dashboard 渲染 forecast 结果
- **THEN** 页面 MUST 继续展示多 agent 的分析原因列表，而不是把这些信息折叠成单一摘要

#### Scenario: Candlestick chart remains intact
- **WHEN** Dashboard 渲染行情区
- **THEN** 页面 MUST 继续展示现有 K 线图组件及其数据来源，不得移除或替换为新的图表模块

#### Scenario: News and sentiment remain intact
- **WHEN** Dashboard 渲染补充信息区
- **THEN** 页面 MUST 继续展示最新市场新闻和情绪模块，不得将其重构为新的信息流页面
