# GoldFXGraph 现代化看板与日线 K 线实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal：** 把黄金研究看板升级成更现代的无衬线视觉，并补上基于数据库的黄金日线 K 线图、带时间戳的风险提示，以及带重点高亮的 agent 结论展示。

**Architecture：** 后端补一个面向前端的日线行情读取接口，直接从 `market_data_bars` 读取最近完成的 OHLC 数据，确保 K 线图不再依赖 CSV 或 forecast 派生。前端保留现有研究数据结构，但把展示层拆成更清晰的模块：行情 K 线、研究摘要、风险提示、agent 重点结论。视觉层统一改成现代无衬线体系，并通过颜色、徽标和局部高亮突出关键句。

**Tech Stack：** FastAPI、SQLAlchemy async、Pydantic、Vue 3、TypeScript、Vite、Tailwind CSS、SVG。

---

### Task 1: 后端暴露黄金日线查询接口

**Files：**
- Modify: `src/goldfxgraph/persistence/repositories.py`
- Modify: `src/goldfxgraph/api/routes.py`
- Modify: `tests/test_market_data_repository.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

在 `tests/test_market_data_repository.py` 增加一个针对 `get_recent_market_bars(symbol="XAUUSD", limit=20)` 的测试，先写入 30 条按日期递增的 `DailyBar`，断言返回结果：
```python
bars = await repository.get_recent_market_bars("XAUUSD", limit=20)
assert len(bars) == 20
assert bars[0].date.isoformat() == "2024-01-11"
assert bars[-1].date.isoformat() == "2024-01-30"
```

在 `tests/test_api.py` 增加一个接口测试，调用 `GET /api/v1/market-data/bars?symbol=XAUUSD&limit=20`，断言返回 JSON 数组且最后一条是最近日期。

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/test_market_data_repository.py::test_get_recent_market_bars_returns_latest_window -q
uv run pytest tests/test_api.py::test_get_market_data_bars_endpoint_returns_recent_daily_bars -q
```
Expected: fail because repository method and API endpoint are not implemented yet.

- [ ] **Step 3: Write minimal implementation**

在 `src/goldfxgraph/persistence/repositories.py` 增加：
```python
async def get_recent_market_bars(self, symbol: str = "XAUUSD", limit: int = 60) -> list[DailyBar]:
    normalized_symbol = _normalize_symbol(symbol)
    async with self._session_factory.sessionmaker() as session:
        statement = (
            select(MarketDataBarModel)
            .where(MarketDataBarModel.symbol == normalized_symbol)
            .order_by(MarketDataBarModel.bar_date.desc(), MarketDataBarModel.id.desc())
            .limit(limit)
        )
        result = await session.execute(statement)
        models = list(result.scalars().all())
        return [_daily_bar_from_model(model) for model in reversed(models)]
```

在 `src/goldfxgraph/api/routes.py` 增加：
```python
@router.get("/market-data/bars", response_model=list[DailyBar])
async def get_market_data_bars(request: Request, symbol: str = "XAUUSD", limit: int = 60) -> list[DailyBar]:
    repository = _repository(request)
    return await repository.get_recent_market_bars(symbol=symbol, limit=limit)
```

让 `limit` 限制在一个合理范围，例如 `1..180`，防止前端误拉太多数据。

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_market_data_repository.py::test_get_recent_market_bars_returns_latest_window -q
uv run pytest tests/test_api.py::test_get_market_data_bars_endpoint_returns_recent_daily_bars -q
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/goldfxgraph/persistence/repositories.py src/goldfxgraph/api/routes.py tests/test_market_data_repository.py tests/test_api.py
git commit -m "feat: expose recent xauusd market bars api"
```

### Task 2: 前端接入日线数据并绘制 K 线图

**Files：**
- Modify: `apps/web/src/types/forecast.ts`
- Modify: `apps/web/src/services/forecastApi.ts`
- Create: `apps/web/src/components/MarketCandlestickChart.vue`
- Modify: `apps/web/src/pages/GoldForecastDashboard.vue`
- Modify: `apps/web/src/constants/forecast.ts`

- [ ] **Step 1: Write the failing test**

前端没有单元测试框架时，用类型检查作为约束。先在 `apps/web/src/services/forecastApi.ts` 和 `apps/web/src/types/forecast.ts` 引入 `DailyBar` 类型、`fetchRecentMarketBars()` 方法，然后立即运行：
```bash
cd apps/web && npm run typecheck
```
Expected: fail until `fetchRecentMarketBars` 和 `DailyBar` 被完整接线。

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd apps/web && npm run typecheck
```
Expected: fail because market bar types, service function, or component props are still missing.

- [ ] **Step 3: Write minimal implementation**

在 `apps/web/src/types/forecast.ts` 增加市场日线类型复用 `DailyBar`：
```ts
export interface DailyBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
  source?: string | null;
  symbol?: string;
}
```

在 `apps/web/src/services/forecastApi.ts` 增加：
```ts
export async function fetchRecentMarketBars(symbol = "XAUUSD", limit = 60): Promise<DailyBar[]> {
  const response = await fetch(buildUrl(`/api/v1/market-data/bars?symbol=${encodeURIComponent(symbol)}&limit=${limit}`), {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error("无法加载黄金日线数据");
  }
  return (await response.json()) as DailyBar[];
}
```

创建 `apps/web/src/components/MarketCandlestickChart.vue`，使用 SVG 渲染蜡烛线、上下影线、最新一根高亮和最近价格标签。组件输入只接受已经按日期升序排列的 `DailyBar[]`。

在 `GoldForecastDashboard.vue` 新增一个“黄金日线”区域，加载最近 60 根日线并传给 K 线组件；加载失败时显示空态，而不是用 forecast 里的 OHLC 代替。

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd apps/web && npm run typecheck
cd apps/web && npm run build
```
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/types/forecast.ts apps/web/src/services/forecastApi.ts apps/web/src/components/MarketCandlestickChart.vue apps/web/src/pages/GoldForecastDashboard.vue apps/web/src/constants/forecast.ts
git commit -m "feat: add xauusd daily candle chart to dashboard"
```

### Task 3: 风险提示加时间戳并重组为更现代的卡片

**Files：**
- Modify: `apps/web/src/pages/GoldForecastDashboard.vue`
- Modify: `apps/web/src/styles/main.css`

- [ ] **Step 1: Write the failing test**

用本地构建作为视觉和结构验证门槛。先把风险区域改成两行元信息：
```vue
<div class="risk-meta">
  <span>研究生成时间：{{ formatDateTime(forecast.reference_time) }}</span>
  <span>数据参考时间：{{ formatDateTime(forecast.data_timestamp) }}</span>
</div>
```

再运行：
```bash
cd apps/web && npm run typecheck
```
Expected: fail until模板和样式都补齐。

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd apps/web && npm run typecheck
```
Expected: fail because `risk-meta` 结构和样式还没落地。

- [ ] **Step 3: Write minimal implementation**

在 `apps/web/src/pages/GoldForecastDashboard.vue` 的风险面板顶部增加时间戳元信息，并把风险内容改成“头部信息 + 列表项”结构；每条风险提示保留原文，但在视觉上加更强的边框、间距和时间标签。

在 `apps/web/src/styles/main.css`：
```css
@import url("https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@300;400;500;700;900&family=Fira+Code:wght@400;500;600;700&display=swap");

:root {
  font-family: "Manrope", "Noto Sans SC", system-ui, sans-serif;
}

.section-heading,
.display-title {
  font-family: "Manrope", "Noto Sans SC", sans-serif;
  letter-spacing: -0.02em;
}
```

把现有带衬线的标题字体移除，保留代码/数字类元素使用 `Fira Code`，让整体视觉更像现代终端而不是内容站。

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd apps/web && npm run typecheck
cd apps/web && npm run build
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/pages/GoldForecastDashboard.vue apps/web/src/styles/main.css
git commit -m "style: modernize dashboard typography and risk panel"
```

### Task 4: agent 重点内容高亮与视觉层级强化

**Files：**
- Modify: `apps/web/src/pages/GoldForecastDashboard.vue`
- Modify: `apps/web/src/constants/forecast.ts`

- [ ] **Step 1: Write the failing test**

先定义重点词高亮规则，例如：
```ts
const HIGHLIGHT_TERMS = ["美联储", "CFTC", "五角大楼披萨指数", "美元指数", "实际利率", "风险"];
```

在页面里把 summary 文本拆成“普通文本 + 高亮片段”，并给关键实体一个专用样式。随后运行：
```bash
cd apps/web && npm run typecheck
```
Expected: fail until高亮渲染逻辑和样式钩子就位。

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd apps/web && npm run typecheck
```
Expected: fail because高亮分段函数、样式类或组件还未实现。

- [ ] **Step 3: Write minimal implementation**

在 `GoldForecastDashboard.vue` 中，把 `news_summary`、`market_sentiment_summary`、`alt_data_summary` 渲染成多行高亮块：
```vue
<span v-for="segment in highlightedSegments(section.content)" :class="segment.highlight ? 'summary-highlight' : 'summary-plain'">
  {{ segment.text }}
</span>
```

给关键 agent 结果增加“重点结论”标签，例如：
- 新闻：突出“新闻流已抓取”“整体情绪”
- 市场情绪：突出“CFTC”“新闻流”“看多/看空”
- 另类数据：突出“五角大楼披萨指数”“美元指数”“实际利率”

在 `apps/web/src/styles/main.css` 新增：
```css
.summary-highlight {
  @apply rounded-lg bg-emerald-500/15 px-1.5 py-0.5 font-semibold text-emerald-100;
}

.summary-plain {
  @apply text-emerald-100/78;
}
```

让 agent 的重点句和普通说明在视觉上有明确层次，而不是整段等权重显示。

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd apps/web && npm run typecheck
cd apps/web && npm run build
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/pages/GoldForecastDashboard.vue apps/web/src/constants/forecast.ts
git commit -m "feat: highlight key agent insights on dashboard"
```

### Task 5: 端到端验收

**Files：**
- All modified files above

- [ ] **Step 1: Run backend verification**

Run:
```bash
uv run pytest tests/test_api.py tests/test_market_data_repository.py tests/test_workflow.py -q
uv run ruff check src tests
```
Expected: PASS.

- [ ] **Step 2: Run frontend verification**

Run:
```bash
cd apps/web && npm run typecheck
cd apps/web && npm run build
```
Expected: PASS.

- [ ] **Step 3: Live smoke test**

启动后端后调用：
```bash
curl -sS http://127.0.0.1:8000/api/v1/market-data/bars?symbol=XAUUSD&limit=20
```
确认返回的日线是数据库中的最近 20 条，并且顺序是从旧到新。随后打开前端页面，确认：
- 风险提示区显示两条时间戳
- K 线图实际显示数据库里的黄金日线
- agent 的重点句有高亮样式
- 字体已切换为现代无衬线风格

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "feat: modernize dashboard and add xauusd daily candles"
```

