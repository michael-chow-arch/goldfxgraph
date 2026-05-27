# 市场时段标签实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在“现代研究台”标题旁增加一个自动判断的市场时段标签，展示日本市、欧洲市、伦敦市、美国市或休市。

**Architecture:** 采用前端本地计算方式，直接根据 UTC 时间与交易时段窗口判断当前状态，不新增后端接口。将时段判断逻辑放在 `GoldForecastDashboard.vue` 内部，配合全局样式表增加对应 pill 视觉样式，保持页面现有视觉体系统一。

**Tech Stack:** Vue 3、TypeScript、Vite、Tailwind CSS、现有全局样式表

---

### Task 1: 前端市场时段判断

**Files:**
- Modify: `apps/web/src/pages/GoldForecastDashboard.vue`

- [ ] **Step 1: 先写出时段判断函数**

```ts
function getMarketSessionLabel(now: Date = new Date()): string {
  const utcDay = now.getUTCDay();
  const minutes = now.getUTCHours() * 60 + now.getUTCMinutes();
  const fridayClose = 22 * 60;
  const japanEnd = 7 * 60;
  const europeEnd = 8 * 60;
  const londonEnd = 13 * 60 + 30;
  const usEnd = 21 * 60;

  if (utcDay === 6) return "休市";
  if (utcDay === 5 && minutes >= fridayClose) return "休市";
  if (utcDay === 0 && minutes < fridayClose) return "休市";
  if (minutes >= 13 * 60 + 30 && minutes < usEnd) return "美国市";
  if (minutes >= 8 * 60 && minutes < londonEnd) return "伦敦市";
  if (minutes >= japanEnd && minutes < 8 * 60) return "欧洲市";
  return "日本市";
}
```

- [ ] **Step 2: 把计算结果接到标题旁边**

```vue
<div class="flex flex-wrap items-center gap-3">
  <p class="panel-title">GoldFXGraph / XAUUSD 研究看板</p>
  <span class="status-pill" :class="statusPillClass">{{ stateLabel }}</span>
  <span class="status-pill" :class="marketSessionClass">{{ marketSessionLabel }}</span>
  <span class="status-pill status-pill--neutral">现代研究台</span>
</div>
```

- [ ] **Step 3: 新增 computed 状态**

```ts
const marketSessionLabel = computed(() => getMarketSessionLabel());

const marketSessionClass = computed(() => {
  const label = marketSessionLabel.value;
  if (label === "美国市") return "status-pill--market-us";
  if (label === "伦敦市") return "status-pill--market-london";
  if (label === "欧洲市") return "status-pill--market-eu";
  if (label === "日本市") return "status-pill--market-jp";
  return "status-pill--market-closed";
});
```

- [ ] **Step 4: 本地验证标题区域布局**

```bash
cd apps/web
npm run typecheck
npm run build
```

---

### Task 2: 市场时段 pill 样式

**Files:**
- Modify: `apps/web/src/styles/main.css`

- [ ] **Step 1: 增加不同市场时段的视觉样式**

```css
.status-pill--market-jp {
  @apply border-cyan-300/35 bg-cyan-500/10 text-cyan-100;
}

.status-pill--market-eu {
  @apply border-violet-300/35 bg-violet-500/10 text-violet-100;
}

.status-pill--market-london {
  @apply border-sky-300/35 bg-sky-500/10 text-sky-100;
}

.status-pill--market-us {
  @apply border-rose-300/35 bg-rose-500/10 text-rose-100;
}

.status-pill--market-closed {
  @apply border-slate-300/25 bg-slate-500/10 text-slate-100;
}
```

- [ ] **Step 2: 检查与现有 `status-pill` 的兼容性**

```bash
cd apps/web
npm run build
```

---

### Task 3: 视觉回归检查

**Files:**
- Verify: `apps/web/src/pages/GoldForecastDashboard.vue`
- Verify: `apps/web/src/styles/main.css`

- [ ] **Step 1: 打开前端页面确认标题栏无换行错位**

```bash
cd apps/web
npm run dev -- --host 0.0.0.0
```

- [ ] **Step 2: 在浏览器中确认市场时段标签显示正确**

```text
访问本地预览页，检查不同 UTC 时间下标签是否显示为 日本市 / 欧洲市 / 伦敦市 / 美国市 / 休市
```

- [ ] **Step 3: 记录最终视觉结果**

```text
确认标题旁标签在桌面和移动端都保持单行或合理换行，不影响“现代研究台”的主视觉层级。
```
