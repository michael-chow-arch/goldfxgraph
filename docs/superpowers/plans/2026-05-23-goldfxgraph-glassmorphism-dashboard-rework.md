# GoldFXGraph Glassmorphism Dashboard Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有研究功能、数据流和 API 的前提下，把 XAUUSD 研究看板重构为带有 Glassmorphism 质感的暗黑金融/科技/黄金/美元 Dashboard 页面，突出现代设计感、视觉层次与信息密度。

**Architecture:** 保持前端单页入口和现有 `fetchLatestForecast()` 数据流不变，只重做页面布局与视觉系统。页面将从“纵向信息列表”改为“英雄区 + 玻璃卡片 Bento 栅格 + 右侧摘要/风险/免责声明”的看板结构；所有状态页、空态、错误态与加载态继续复用现有交互，只调整排版和视觉层级。样式层集中收敛到 `apps/web/src/styles/main.css`，避免把玻璃拟态、背景光效和卡片样式散落在组件里。

**Tech Stack:** Vue 3, TypeScript, Vite, Tailwind CSS, 现有 `forecastApi.ts`、`forecast.ts` 类型和 `GoldForecastDashboard.vue`

---

### Task 1: 重新设计页面结构，建立玻璃拟态金融看板主布局

**Files:**
- Modify: `apps/web/src/pages/GoldForecastDashboard.vue`

- [ ] **Step 1: 读取现有页面的数据流和状态分支**

确认以下现有能力必须原样保留并继续使用：
```ts
fetchLatestForecast()
isLoading
errorMessage
forecast
retry()
onMounted(() => void loadForecast())
```

- [ ] **Step 2: 把首屏改成更现代的 Hero + 快照结构**

在 `GoldForecastDashboard.vue` 中把页面主内容改成以下层级：
```vue
<main>
  <div class="dashboard-shell">
    <header class="hero-panel">
      <!-- 品牌标题、状态胶囊、中文简介 -->
      <!-- 右侧当前价格、方向、置信度、数据时间、数据来源 -->
    </header>

    <!-- loading / error / empty 保持现有逻辑 -->

    <section v-else class="dashboard-grid">
      <!-- 研究快照 -->
      <!-- 研究摘要 -->
      <!-- 风险提示 -->
      <!-- 智能体投票 -->
      <!-- 交易研究 -->
      <!-- 日线 OHLC -->
      <!-- 免责声明 -->
    </section>
  </div>
</main>
```

主视觉要求：
```ts
glassmorphism
dark mode
gold accent
tech finance mood
Chinese UI text
high information density
```

- [ ] **Step 3: 重新组织内容卡片优先级**

把信息按照下面顺序呈现：
```text
1. 当前价格与方向
2. 置信度与盈亏比
3. 数据时间、数据来源、运行编号
4. 研究摘要
5. 风险提示
6. 智能体投票
7. 交易研究字段
8. 日线 OHLC
9. 免责声明
```

要求保持这些现有字段继续展示：
```ts
symbol
reference_time
data_timestamp
data_source
current_price
daily_open
daily_high
daily_low
daily_close
direction
entry_price
take_profit_price
stop_loss_price
holding_period
intraday_action
long_term_action
confidence_score
technical_summary
macro_summary
news_summary
risk_summary
agent_votes
risk_notes
disclaimer
```

- [ ] **Step 4: 保留状态页语义，但换成统一的玻璃拟态外观**

继续保留并优化：
```vue
v-if="isLoading"
v-else-if="errorMessage"
v-else-if="!forecast"
v-else
```

确保：
```ts
loading 使用骨架/脉冲提示
错误页有清晰恢复按钮
空态有明确行动按钮
全部文案保持中文
```

### Task 2: 重做视觉系统，让页面具备暗黑玻璃拟态金融科技感

**Files:**
- Modify: `apps/web/src/styles/main.css`

- [ ] **Step 1: 建立新的全局视觉基调**

把全局背景改成更适合金融科技仪表盘的暗黑层级：
```css
body {
  background:
    radial-gradient(circle at 18% 12%, rgba(251, 191, 36, 0.16), transparent 20%),
    radial-gradient(circle at 82% 14%, rgba(59, 130, 246, 0.12), transparent 18%),
    radial-gradient(circle at 50% 0%, rgba(16, 185, 129, 0.08), transparent 24%),
    linear-gradient(180deg, rgba(2, 6, 23, 0.98) 0%, #020617 36%, #01040c 100%);
}
```

- [ ] **Step 2: 增加玻璃拟态卡片与背景层**

新增/强化以下类名，供 `GoldForecastDashboard.vue` 统一使用：
```css
.hero-panel
.dashboard-shell::before
.dashboard-shell > *
.metric-card--glass
.metric-card--hero
.data-chip
.signal-metric
.section-heading
.display-title
.price-display
```

视觉要求：
```ts
backdrop-filter blur
subtle border
soft shadow
gold highlight
deep black / midnight blue base
```

- [ ] **Step 3: 让交互态更像高端仪表盘而不是普通卡片**

需要确保下面元素都有明确 hover / focus / loading 反馈：
```css
.action-button
.status-pill
.metric-card
.data-chip
```

要求：
```ts
hover 不引起布局抖动
transition 150-300ms
focus-visible 清晰可见
prefers-reduced-motion 兼容
```

- [ ] **Step 4: 保持中文字体阅读体验，同时保留数据感**

建议使用：
```css
font-family: "Noto Sans SC"
font-family: "Noto Serif SC"
font-family: "Fira Code"
```

其中：
```ts
中文正文 = Noto Sans SC
标题 = Noto Serif SC 或 Noto Sans SC
价格/数据/ID = Fira Code
```

### Task 3: 验证前端构建与页面功能没有被视觉重构破坏

**Files:**
- Test: `apps/web/package.json`
- Test: `apps/web/src/pages/GoldForecastDashboard.vue`
- Test: `apps/web/src/styles/main.css`

- [ ] **Step 1: 跑类型检查**

Run:
```bash
cd apps/web
npm run typecheck
```

Expected:
```text
0 errors
```

- [ ] **Step 2: 跑生产构建**

Run:
```bash
cd apps/web
npm run build
```

Expected:
```text
vite build 完成，无 Tailwind 或 Vue 编译错误
```

- [ ] **Step 3: 复查关键用户路径**

确认这些路径仍然可用：
```ts
页面打开后自动加载最新研究结果
错误态可点击“手动刷新”重试
空态有明确提示和按钮
所有研究字段仍在页面上可见
```

- [ ] **Step 4: 记录最终交付内容**

在完成时列出实际修改的文件，并确认没有改动后端或数据源逻辑：
```text
仅前端重构
现有 API 保持不变
现有数据字段保持不变
```
