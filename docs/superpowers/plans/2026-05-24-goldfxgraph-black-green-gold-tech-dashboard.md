# GoldFXGraph 黑绿金赛博 Dashboard 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 XAUUSD Dashboard 重构为黑绿金赛博研究终端，强化首屏信号层级、降低重复信息、保持现有功能和数据流不变。

**Architecture:** 仅重构前端页面与全局样式，不改后端 API 和数据模型。页面采用“信号 → 理由 → 共识 → 行动 → 支撑信息”的信息顺序，视觉上使用深墨绿黑底、霓虹绿高亮、金色点睛和少量冷青辅助，所有卡片保持玻璃拟态但控制透明度以确保可读性。

**Tech Stack:** Vue 3, TypeScript, Vite, Tailwind CSS

---

### Task 1: 定义黑绿金主题变量与全局卡片视觉

**Files:**
- Modify: `/Users/admin/.codex/worktrees/4889/goldfxgraph/apps/web/src/styles/main.css`

- [ ] **Step 1: 先确认当前样式基线**

  运行：

  ```bash
  sed -n '1,260p' /Users/admin/.codex/worktrees/4889/goldfxgraph/apps/web/src/styles/main.css
  ```

  关注点：当前是否仍存在浅色蓝白样式、是否还有黑底遗留、是否有不合法的 Tailwind 透明度值。

- [ ] **Step 2: 写入黑绿金的全局样式**

  目标样式应覆盖：

  ```css
  @layer base {
    :root {
      color: #eaf7ee;
      background-color: #020805;
      font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
    }

    html {
      background-color: #020805;
      color: #eaf7ee;
    }

    body {
      margin: 0;
      min-width: 320px;
      min-height: 100vh;
      background:
        radial-gradient(circle at 16% 12%, rgba(46, 230, 107, 0.18), transparent 18%),
        radial-gradient(circle at 84% 10%, rgba(245, 197, 66, 0.14), transparent 16%),
        radial-gradient(circle at 50% 0%, rgba(7, 21, 14, 0.9), transparent 18%),
        radial-gradient(circle at 50% 100%, rgba(39, 199, 255, 0.08), transparent 24%),
        linear-gradient(180deg, #020805 0%, #04110a 38%, #07150e 100%);
      color: #eaf7ee;
      background-attachment: fixed;
    }
  }

  @layer components {
    .dashboard-shell::before {
      background-image:
        linear-gradient(rgba(143, 168, 160, 0.08) 1px, transparent 1px),
        linear-gradient(90deg, rgba(143, 168, 160, 0.08) 1px, transparent 1px);
    }

    .dashboard-panel {
      @apply relative overflow-hidden border border-emerald-400/18 bg-[#04110a]/82 shadow-[0_30px_80px_-42px_rgba(0,0,0,0.55)] backdrop-blur-2xl;
    }

    .hero-panel {
      background:
        linear-gradient(145deg, rgba(4, 17, 10, 0.95), rgba(2, 8, 5, 0.82)),
        radial-gradient(circle at top right, rgba(46, 230, 107, 0.2), transparent 24%),
        radial-gradient(circle at 16% 18%, rgba(245, 197, 66, 0.16), transparent 20%);
    }

    .panel-title { @apply font-mono text-[11px] font-semibold tracking-[0.18em] text-emerald-300; }
    .metric-label { @apply font-mono text-[11px] tracking-[0.16em] text-emerald-200/70; }
    .metric-value { @apply font-mono text-lg font-semibold text-[#eaf7ee]; }
  }
  ```

  同时把主要组件类同步到黑绿金语义：

  ```css
  .metric-card { @apply rounded-2xl border border-emerald-400/18 bg-[#07150e]/78 px-4 py-3.5 backdrop-blur-xl transition-all duration-200 hover:border-emerald-300/40 hover:bg-[#0b1d13]/90; }
  .metric-card--hero { @apply border-emerald-300/20 bg-[#06130d]/92 p-5; }
  .metric-card--accent { @apply border-amber-300/24 bg-amber-500/10 hover:border-amber-300/40 hover:bg-amber-500/14; }
  .status-pill--loading { @apply border-emerald-300/35 bg-emerald-500/10 text-emerald-300; }
  .status-pill--danger { @apply border-rose-400/35 bg-rose-500/10 text-rose-300; }
  .status-pill--success { @apply border-emerald-400/35 bg-emerald-500/12 text-emerald-300; }
  .status-pill--neutral { @apply border-amber-300/28 bg-amber-500/10 text-amber-200; }
  .data-chip { @apply inline-flex min-h-11 items-center gap-3 rounded-2xl border border-emerald-400/18 bg-[#07150e]/82 px-4 py-2.5 text-sm; }
  .price-display { @apply font-mono text-4xl font-semibold tracking-tight text-amber-200 sm:text-5xl; }
  ```

- [ ] **Step 3: 确认没有非法 Tailwind 透明度**

  运行：

  ```bash
  rg -n "bg-[a-z-]+/[0-9]{2,3}" /Users/admin/.codex/worktrees/4889/goldfxgraph/apps/web/src/styles/main.css
  ```

  如果出现 `82`、`86` 这类非法值，改成 Tailwind 支持的透明度，例如 `80`、`90`、`75`、`70`。

---

### Task 2: 重排 GoldForecastDashboard 的信息层级

**Files:**
- Modify: `/Users/admin/.codex/worktrees/4889/goldfxgraph/apps/web/src/pages/GoldForecastDashboard.vue`
- Modify: `/Users/admin/.codex/worktrees/4889/goldfxgraph/apps/web/src/constants/forecast.ts`

- [ ] **Step 1: 先收紧顶部 Hero 和 chips**

  目标是让首屏只保留最关键的信号，不再重复展示同一批数据。

  当前建议的 Hero 信息顺序：

  1. 大标题：`黄金研究指挥台`
  2. 状态胶囊：加载 / 已同步 / 失败
  3. 主价格卡：当前价格 + 方向 + 置信度条
  4. 研究 chips：标的、置信度
  5. 主题说明：黑绿金赛博风、手动刷新

  需要把顶部 chips 保持在 2 到 3 个，避免同时展示方向、置信度、价格、盈亏比和来源这种重复信号。

- [ ] **Step 2: 把“研究摘要”和“风险提示”合并成主研究区**

  结构建议：

  - 左侧：技术 / 宏观 / 新闻 / 风险四个摘要卡
  - 右侧：风险提示独立强化块

  这样可避免“研究摘要”和“风险提示”在页面上彼此打散。

- [ ] **Step 3: 把智能体投票改成核心模块**

  投票区需要满足：

  - 桌面端表格必须清晰显示：智能体、方向、置信度、理由
  - 移动端使用卡片列表
  - 表头、表体、hover、边框全部切到深色玻璃风
  - 不允许再出现浅色投票表格或黑底回退样式

  建议保留如下表结构：

  ```vue
  <table class="min-w-full divide-y divide-emerald-400/12">
    <thead class="bg-[#07150e]/90">
      <tr>
        <th class="px-4 py-3 text-left font-mono text-[11px] tracking-[0.18em] text-emerald-200/70">智能体</th>
        <th class="px-4 py-3 text-left font-mono text-[11px] tracking-[0.18em] text-emerald-200/70">方向</th>
        <th class="px-4 py-3 text-left font-mono text-[11px] tracking-[0.18em] text-emerald-200/70">置信度</th>
        <th class="px-4 py-3 text-left font-mono text-[11px] tracking-[0.18em] text-emerald-200/70">理由</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-emerald-400/12 bg-[#06130d]/88">
      ...
    </tbody>
  </table>
  ```

- [ ] **Step 4: 把交易研究字段放在“行动卡”里**

  行动区建议顺序：

  1. 入场价
  2. 止盈价
  3. 止损价
  4. 风险回报比
  5. 建议持有周期
  6. 日内建议
  7. 中长期建议

  风格上让入场和止盈偏金色，止损偏更醒目的红色，但不要过饱和。

- [ ] **Step 5: 把元数据、OHLC、免责声明压到后段**

  这些模块的定位是“支撑信息”，不应该抢首屏。

  推荐后段顺序：

  1. 实时元数据
  2. 日线 OHLC
  3. 免责声明

- [ ] **Step 6: 同步更新中文标签**

  需要检查并统一以下标签：

  - `研究看板`
  - `实时价格快照`
  - `多智能体摘要`
  - `智能体投票`
  - `结构化交易字段`
  - `实时元数据`
  - `日线 OHLC`
  - `免责声明`

  `apps/web/src/constants/forecast.ts` 中的 Agent 标签保持中文，例如：

  ```ts
  export const AGENT_LABELS: Record<string, string> = {
    technical: "技术分析",
    macro: "宏观分析",
    news: "新闻分析",
    risk: "风险分析",
    planner: "预测规划",
  };
  ```

---

### Task 3: 跑前端验证并修复样式问题

**Files:**
- Modify: `/Users/admin/.codex/worktrees/4889/goldfxgraph/apps/web/src/pages/GoldForecastDashboard.vue`
- Modify: `/Users/admin/.codex/worktrees/4889/goldfxgraph/apps/web/src/styles/main.css`

- [ ] **Step 1: 运行类型检查**

  运行：

  ```bash
  cd /Users/admin/.codex/worktrees/4889/goldfxgraph/apps/web && npm run typecheck
  ```

  预期：通过。

- [ ] **Step 2: 运行构建**

  运行：

  ```bash
  cd /Users/admin/.codex/worktrees/4889/goldfxgraph/apps/web && npm run build
  ```

  预期：通过，且不会再出现非法 Tailwind 类或样式解析错误。

- [ ] **Step 3: 修复构建期间暴露的问题**

  若构建失败，优先检查：

  - 是否存在非法 Tailwind 透明度类
  - 是否有未使用的计算属性或导入
  - 是否还有残留的浅色主题类或黑底回退类

  修复后重新执行 `npm run typecheck` 和 `npm run build`。

- [ ] **Step 4: 复查 diff**

  运行：

  ```bash
  git -C /Users/admin/.codex/worktrees/4889/goldfxgraph diff -- apps/web/src/pages/GoldForecastDashboard.vue apps/web/src/styles/main.css apps/web/src/constants/forecast.ts
  ```

  重点确认：

  - 没有把后端或无关文件一起改进去
  - 没有重复内容回流
  - 智能体投票区域已完全切换到深色玻璃风
  - 页面整体保持黑绿金科技风，而不是回到蓝白或黑金混搭

---

### Task 4: 收尾与交接

**Files:**
- Optional: `/Users/admin/.codex/worktrees/4889/goldfxgraph/docs/superpowers/plans/2026-05-24-goldfxgraph-black-green-gold-tech-dashboard.md`

- [ ] **Step 1: 标记计划完成**

  把每个任务的完成情况写回计划文件的任务清单。

- [ ] **Step 2: 总结最终变化**

  输出最终摘要时需要说明：

  - 视觉主题已切为黑绿金赛博风
  - 页面内容顺序已重排
  - 智能体投票不再是黑底
  - 重复内容已被收敛
  - typecheck / build 是否通过

---

## 自检结果

- 已覆盖视觉主题、内容重排、投票区修正和构建验证。
- 未包含任何占位符或模糊任务。
- 文件边界清晰：`main.css` 负责主题与全局卡片，`GoldForecastDashboard.vue` 负责布局与内容，`forecast.ts` 负责中文标签和方向样式。
- 计划范围单一，可直接执行，不需要拆分为多个子项目。
