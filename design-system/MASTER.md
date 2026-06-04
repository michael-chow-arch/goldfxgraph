# GoldFXGraph Design System

## 设计目标

GoldFXGraph 是一个面向 XAUUSD 黄金研究的 AI-native financial research cockpit。它不是普通交易页面，也不是普通报表页面，而是一个用于查看研究结论、执行轨迹、Agent reasoning、tool calls、checkpoint、human review 与 forecast evaluation 的专业研究台。

## 核心设计原则

1. 先结论，后证据，再轨迹
   - 首屏必须先呈现方向、当前价格、置信度、执行建议。
   - 证据包、workflow 轨迹和验证信息只能服务于结论，不可抢占主视觉。

2. 高信息密度，但保持可扫读
   - 允许密集数据，但必须通过清晰分层、固定语义和稳定间距控制复杂度。
   - 禁止把所有内容都做成同等视觉权重的卡片。

3. 暗色为主，金色点睛
   - 背景采用深色研究台风格。
   - 金色只用于关键结论和高价值数值，不可滥用。
   - 蓝色用于技术层、信息层和链接层。
   - 绿色/红色仅用于明确涨跌和风险含义。

4. 状态优先于装饰
   - loading、empty、error、stale、partial success 必须清晰表达。
   - 状态块必须提供下一步行动或恢复路径。

5. 视觉语义必须统一
   - 同一类信息必须使用同一类组件和视觉语法。
   - 不允许不同页面各自定义一套“相似但不一致”的卡片、标签和面板风格。

## 品牌气质

- 专业
- 克制
- 高级
- 冷静
- 机构级
- 数据驱动
- AI-native

禁止气质：

- 炫技
- 游戏化
- HUD 霓虹风
- 过度发光
- 普通营销站风
- 过多装饰性渐变

## 色彩系统

### 基础背景

- `bg-canvas`: `#020617`
- `bg-surface-1`: `#0B1220`
- `bg-surface-2`: `#111A2B`
- `bg-surface-3`: `#162033`
- `bg-surface-inset`: `#0F172A`

### 边界与分割

- `border-subtle`: `rgba(148, 163, 184, 0.14)`
- `border-strong`: `rgba(148, 163, 184, 0.24)`
- `border-accent`: `rgba(212, 167, 44, 0.32)`

### 文本

- `text-primary`: `#F8FAFC`
- `text-secondary`: `#94A3B8`
- `text-muted`: `#64748B`
- `text-inverse`: `#0F172A`

### 语义色

- `accent-gold`: `#D4A72C`
- `accent-amber`: `#F59E0B`
- `accent-blue`: `#38BDF8`
- `accent-green`: `#22C55E`
- `accent-red`: `#EF4444`
- `accent-orange`: `#F97316`

### 使用规则

- 金色仅用于关键结论、当前价格、最重要的 CTA 和高价值数字。
- 蓝色用于 workflow、metadata、tool calls、技术分析和链接。
- 绿色表示正向确认，红色表示风险或失效，不承担装饰任务。
- 禁止以紫色、粉色或彩虹渐变作为主视觉。

## 字体系统

### 推荐组合

- `Heading`: `Plus Jakarta Sans`
- `Body`: Apple system Chinese stack
- `Numeric / Meta / Label`: `Fira Code`
- `Chinese fallback`: `PingFang SC`, `Hiragino Sans GB`, `Noto Sans SC`

### 使用规则

- 标题使用更具品牌感的无衬线字体，增强产品高级感。
- 正文优先使用苹果系中文系统字体，以获得更自然的中文排版观感。
- 数字、时间、状态、标签使用等宽字体，提升“研究台”和“数据系统”气质。

### 文字层级规范

页面中只允许使用以下 8 种文字角色。任何页面和组件都必须从这些角色中选择，不允许自行定义新的字号、字重、行高或字间距。

| 文字角色 | 用途 | 字号 | 字重 | 行高 | 字体 | 说明 |
|---|---|---:|---:|---:|---|---|
| `display-title` | 页面主标题 / Hero 标题 | 40-48px | 600-700 | 1.05-1.15 | `Plus Jakarta Sans` + 中文 fallback | 仅用于每页最重要的主结论区域 |
| `section-heading` | 模块标题 / 分区标题 | 26-32px | 600-700 | 1.12-1.22 | `Plus Jakarta Sans` + 中文 fallback | 用于卡片、面板、章节标题，必须清晰高于正文 |
| `card-title` | card 内部标题 / 行为标题 | 17-19px | 600-700 | 1.22-1.32 | `Plus Jakarta Sans` + 中文 fallback | 只用于 card 内的次级标题，不能显得像普通注释 |
| `body-lg` | 首屏说明 / 较长正文 | 15-16px | 400-500 | 1.7-1.8 | Apple system Chinese stack | 用于解释性文本、摘要段落 |
| `body-md` | 常规正文 / 详情说明 | 14px | 400-500 | 1.6-1.75 | Apple system Chinese stack | 页面最常见正文 |
| `body-sm` | 辅助说明 / 次级说明 | 12-13px | 400-500 | 1.5-1.6 | Apple system Chinese stack | 用于描述、注释、次级提示 |
| `meta-label` | 标签 / 说明 / 眉标 | 12-13px | 600-700 | 1 | `Fira Code` / `Plus Jakarta Sans` | 用于眉标、label、key-name、时间戳，默认使用金色文字，不再使用嵌套胶囊 |
| `numeric` | 数值 / 价格 / 百分比 / 时间 | 12-32px | 600-700 | 1 | `Fira Code` | 用于价格、置信度、时间、统计值 |

### 文字使用规则

- 主标题只允许出现一次。
- `display-title` 与 `section-heading` 不得在同一页面重复承担主视觉职责。
- 所有数字、百分比、时间、代码、阶段名称必须优先使用 `numeric` 或 `meta-label`。
- 正文与说明统一使用 `body-lg`、`body-md`、`body-sm` 三档，不允许组件自己写一套 `text-sm` 组合。
- 多行说明优先换行，不允许为了紧凑随意压缩字号。
- 任何新的文字样式都必须先补进本表，再在组件中使用。

## 间距与布局

### 间距节奏

- 页面外边距：`24px` 到 `32px`
- 卡片内部 padding：`16px` 到 `24px`
- 组间 spacing：`16px` 到 `32px`
- 模块之间必须有稳定节奏，不允许每个区域随意变化。

### 布局原则

- 一个页面只能有一个主结论区。
- 结论区、执行区、证据区、轨迹区、验证区必须分层。
- 长文本、长列表、长证据必须可折叠或逐步展开。
- 应用级左侧导航应作为固定壳存在，承载研究总览与执行轨迹等核心入口。

## 胶囊与标签系统

页面中只允许使用以下胶囊类型。任何新的胶囊都必须映射到这些语义，而不是自行起一个新的按钮/标签风格。

| 胶囊类型 | 用途 | 视觉 | 规则 |
|---|---|---|---|
| `status-pill` | 状态、阶段、运行结果 | 深色底，细边框，低对比发光 | 用于 loading / success / danger / neutral / market 状态 |
| `analysis-badge` | 研究标签、模块角标、说明标签 | 更小、更克制，强调分类 | 用于“主判断 / 元数据 / 证据 / 风险”等语义标签 |
| `confidence-chip` | 置信度展示 | 双区块结构，数值突出 | 仅用于置信度，不可复用到别的指标 |
| `data-chip` | 首屏结构化摘要 | 轻量、卡片化信息胶囊 | 仅用于首页总览快照 |
| `agent-state-chip` | 智能体状态 | 带点状状态指示 | 用于 workflow / agent 状态展示 |

### 胶囊使用规则

- 同一页面的胶囊类型不能无限增殖。
- 胶囊高度、圆角、字重必须来自组件 token，不允许局部手写。
- 同一语义的胶囊在全项目必须完全一致，不能出现同类信息一会儿黑底、一会儿彩底、一会儿浅底的情况。
- `status-pill` 只表达状态，不承担正文说明。
- `analysis-badge` 只表达分类，不承担主结论。
- `confidence-chip` 只表达置信度，不允许再加其它字段。
- 胶囊标题文字必须遵循 `meta-label` 或 `numeric` 规则。
- label 和 title 优先使用纯文字金色样式，不要把本应是标题的内容再包进新的胶囊里。
- 金色 label / 标题必须足够清晰，优先通过字号、字重和对比度提高可读性，而不是依赖更多装饰。

## 圆角与阴影

### 圆角

- 标准控件：`12px`
- 信息卡片：`16px`
- 主要面板：`20px`
- Hero / 聚焦区域：`24px`

### 阴影

- 只保留少量柔和阴影。
- 阴影是层级提示，不是装饰。
- 禁止每个组件都使用发光、重影或重度高光。

## 组件语义

### 必须统一的基础组件

- `PageShell`
- `SectionHeader`
- `StateBanner`
- `MetricCard`
- `DecisionSummaryCard`
- `ExecutionPlanCard`
- `EvidenceBundleCard`
- `WorkflowTracePanel`
- `ValidationPanel`
- `SkeletonBlock`
- `EmptyStateCard`
- `ErrorRecoveryCard`

### Card 风格规范

所有 card 必须遵循统一的视觉语法，禁止每个组件自定义一套 card 观感。

#### Card 层级

1. `card--hero`
   - 用于首屏主结论区
   - 只允许一个主视觉焦点
   - 标题使用 `display-title` 或 `section-heading`
   - 眉标/标签使用 `meta-label`，并保持金色文字，不使用胶囊包裹

2. `card--surface`
   - 用于常规章节
   - 标题使用 `section-heading` 或 `card-title`
   - 正文使用 `body-md` / `body-sm`
   - 卡片顶部的分类标识若存在，只能使用统一的 `analysis-badge`，不能改成另一套样式

3. `card--embedded`
   - 用于 card 内部的小块内容
   - 标题使用 `meta-label`
   - 数字使用 `numeric`

4. `card--flat`
   - 用于列表、历史、证据行
   - 不允许再加重阴影
   - 只能做轻边界和轻背景分层
   - 仍然必须是深色语义层，禁止白底与浅灰底回归

### Card 标题规则

- 顶层 card 标题默认使用文字，不使用胶囊。
- 只有当 card 的职责是状态/类别时，标题左或右侧才可加 `analysis-badge`。
- card 内正文不允许使用随意的 `text-sm` 组合，必须映射到正文文字角色。
- 同一页面的 card 标题字号必须一致，不能出现多个“看起来像标题”的尺寸系统。

### 使用规则

- 同类信息必须使用同类组件。
- 不允许在不同页面重复发明新的视觉语法。
- 组件命名优先反映信息语义，而不是纯布局。

## 状态规范

### Loading

- 使用 skeleton 或结构化占位。
- 显示“正在加载什么”和“为什么要等”。

### Empty

- 不允许空白页。
- 需要说明原因、条件与下一步建议。

### Error

- 必须有明确错误信息。
- 必须提供恢复动作，例如重试、刷新或返回上一步。

### Stale

- 若数据不是最新完成态，必须明确提示。
- stale 状态不能伪装成 success。

### Partial

- 如果部分模块成功、部分模块失败，必须允许局部降级展示。

## 交互规范

- hover 只做轻微边界、背景或文字变化。
- active 只做轻微按压感。
- 所有可点击区域必须有清晰 hover/active/focus 状态。
- `prefers-reduced-motion` 必须被尊重。
- 动效只用于提示状态变化，不用于炫技。

## 图表规范

- 图表必须服务于结论，不允许成为纯装饰。
- 图表标题应说明图表回答的问题。
- 图表旁必须有关键数值摘要。
- 悬浮提示应短而精确。
- 移动端要保留可读性和最低必要信息。

## 表格与列表规范

- 表格和列表必须有明确列语义。
- 长列表必须支持折叠、分页或局部展开。
- 表格中的状态、方向、时间、数值要用统一格式。

## 研究工作流可视化规范

GoldFXGraph 的差异化核心在于 LangGraph workflow 与 multi-agent reasoning，因此页面必须让用户看见：

- node 顺序
- tool calls
- agent reasoning 摘要
- checkpoint / validation
- human review / repair
- forecast evaluation / scorecard

但这些内容必须以“辅助结论”的方式展示，而不是覆盖结论本身。

## 可访问性

- 文本对比度必须足够。
- 错误状态必须可被屏幕阅读器感知。
- 点击目标要足够大。
- 不能只靠颜色传达信息。
- 键盘可达性必须完整。

## 设计禁忌

- 不要把整个页面做成 HUD 科幻风。
- 不要用大面积炫彩渐变掩盖层级问题。
- 不要让所有卡片看起来一模一样。
- 不要把结论埋在长文本里。
- 不要把状态提示和结论混在同一权重。
- 不要引入大型 UI 框架来掩盖设计系统缺失。
- 不要在组件里随意写 `text-*`、`bg-*`、`border-*` 作为最终语义样式。
- 不要在组件里临时定义新的字体家族、字号、字重、胶囊或 card 变体。

## 页面实施顺序

1. 先重构 dashboard 信息架构。
2. 再统一基础组件。
3. 然后接入 workflow / validation / scorecard 表达。
4. 最后优化响应式和状态体系。

## 维护规则

- 后续所有页面实现必须优先读取本文件。
- page override 文件只允许覆盖具体页面差异，不允许推翻全局系统。
