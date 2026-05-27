# GoldFXGraph Dashboard UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变任何功能、接口和数据契约的前提下，重新设计 GoldFXGraph 的 dashboard 页面视觉层级、布局结构、卡片样式、信息密度、响应式体验和状态展示，让它更像一个专业的金融研究 cockpit。

**Architecture:** 保持现有 Vue 3 + TypeScript + Vite + Tailwind 结构不变，只重排 `GoldForecastDashboard.vue` 的区块顺序和视觉权重，配合 `MarketCandlestickChart.vue` 的局部展示优化以及 `main.css` 的统一设计 token。所有数据仍来自现有 API 与现有类型，不新增 mock、不新增字段、不改请求路径。最终目标是让首屏先给出研究决策，再给出证据和辅助信息。

**Tech Stack:** Vue 3, TypeScript, Tailwind CSS, Vite, existing dashboard API services, existing forecast types

---

### Task 1: 固定页面信息架构与首屏视觉重排

**Files:**
- Modify: `apps/web/src/pages/GoldForecastDashboard.vue`

- [ ] **Step 1: 以当前页面结构为基线，重排首屏和次级区域的视觉顺序**

```vue
<!-- 目标结构：
1. Hero summary：标题、状态、当前价格、方向、置信度、最新执行时间
2. 研究结论与窗口判断：summary cards + window direction cards
3. 结构化交易字段：entry / TP / SL / RR / holding / action
4. 图表和风险区：K 线图与风险提示并列
5. 智能体投票、历史表现、透明度信息、免责声明 -->
```

- [ ] **Step 2: 将核心结论相关元素提升到首屏最显眼位置**

```vue
<!-- 示例目标：
<header>
  <div class="hero-left">标题 + 价格 + 方向 + 置信度 + chips</div>
  <div class="hero-right">调度状态 + 最新执行时间 + 关键元数据</div>
</header>
-->
```

- [ ] **Step 3: 把“研究结论”“风险提示”“交易字段”“K线图”从功能上保持不变，只调整阅读顺序和视觉分区**

```vue
<!-- 保留现有 forecast / schedulerStatus / history / marketBars 数据源，不新增任何字段 -->
```

- [ ] **Step 4: 在页面中明确保留 loading、empty、error 和 success 的独立展示块**

```vue
<!-- 继续使用现有 isLoading、errorMessage、forecast、isStatusLoading、isHistoryLoading、isMarketBarsLoading -->
```

### Task 2: 统一 dashboard 视觉系统与卡片语法

**Files:**
- Modify: `apps/web/src/styles/main.css`
- Modify: `apps/web/src/pages/GoldForecastDashboard.vue`

- [ ] **Step 1: 收敛 dashboard 主视觉为深色金融研究面板风格**

```css
/* 统一背景、边框、阴影和渐变的受控强度，保留深色但减少过强霓虹感 */
```

- [ ] **Step 2: 定义并应用统一卡片家族样式**

```css
/* hero card / metric card / evidence card / risk card / chart card
   统一圆角、边框、内边距、hover、阴影和文字层级 */
```

- [ ] **Step 3: 强化关键文本层级**

```css
/* 当前价格、当日方向、置信度、主判断、综合评价、风险提醒使用更强的字号与颜色层级 */
```

- [ ] **Step 4: 调整 summary / risk / history / transparency 的次级内容样式**

```css
/* 让辅助说明更克制，避免和主结论抢同等权重 */
```

### Task 3: 优化图表区和证据区的展示体验

**Files:**
- Modify: `apps/web/src/components/MarketCandlestickChart.vue`
- Modify: `apps/web/src/pages/GoldForecastDashboard.vue`

- [ ] **Step 1: 精简图表标题区，使其更像研究证据区而不是独立报表页**

```vue
<!-- 保留 title/subtitle/description/current price 信息，但减少解释性文字的视觉占比 -->
```

- [ ] **Step 2: 调整图表统计条、tooltip、最新价提示和边框层次**

```css
/* 确保图表信息清晰，但不压过首屏核心结论 */
```

- [ ] **Step 3: 让图表区和右侧说明区在桌面端形成主次关系，在移动端自然纵向堆叠**

```vue
<!-- 保持现有 bars/currentPrice 传参不变，仅改变布局与视觉表现 -->
```

### Task 4: 重构状态态、响应式与历史区呈现

**Files:**
- Modify: `apps/web/src/pages/GoldForecastDashboard.vue`
- Modify: `apps/web/src/styles/main.css`

- [ ] **Step 1: 重新设计 loading / empty / error 视图，使它们和成功态在视觉上明显分层**

```vue
<!-- loading 使用骨架或占位感，error 使用清晰错误面板，empty 使用引导型空状态 -->
```

- [ ] **Step 2: 调整历史表现、透明度信息和免责声明的视觉顺序与密度**

```vue
<!-- 历史区和免责声明保持底部收口，不抢首屏焦点 -->
```

- [ ] **Step 3: 完成 375px、768px、1024px、1440px 的响应式检查点适配**

```css
/* 375px：单列堆叠
   768px：两列主结构
   1024px+：12 栅格与侧边信息区
*/
```

### Task 5: 运行验证并做视觉回归检查

**Files:**
- Validate only

- [ ] **Step 1: 运行前端类型检查**

```bash
cd /Users/admin/.codex/worktrees/6b12/goldfxgraph/apps/web && npm run typecheck
```

- [ ] **Step 2: 运行前端 lint**

```bash
cd /Users/admin/.codex/worktrees/6b12/goldfxgraph/apps/web && npm run lint
```

- [ ] **Step 3: 运行前端 build**

```bash
cd /Users/admin/.codex/worktrees/6b12/goldfxgraph/apps/web && npm run build
```

- [ ] **Step 4: 用浏览器检查本地 dashboard 的桌面端与窄屏布局，确认没有改动 API 契约或字段名**

```text
检查点：
1. 首屏是否先看到 current price / direction / confidence / latest execution
2. chart、summary、risk、history 是否分层明确
3. 移动端是否单列可读
4. loading / error / empty 是否清晰
```

- [ ] **Step 5: 最终核对只改了展示层文件，未触碰后端接口、TS 字段、路由、store 或 query key**

```text
核对清单：
- 不修改 src/goldfxgraph 下的后端接口
- 不修改 apps/web/src/services/forecastApi.ts 的请求签名
- 不修改 apps/web/src/types/forecast.ts 的字段名称
- 不修改路由和 query key
```
