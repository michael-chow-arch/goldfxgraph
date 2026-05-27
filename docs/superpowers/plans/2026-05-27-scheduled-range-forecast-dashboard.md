# Scheduled Range Forecast Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 GoldFXGraph 改造成一个统一 15 分钟自动调度的黄金研究台，取消手动刷新入口，并让 forecast 以固定时间窗口的方向区间输出，同时在 Dashboard 首屏展示最新执行时间和多智能体运行状态。

**Architecture:** 后端先补齐统一调度状态和窗口化 forecast 的结构化契约，再把现有 workflow 包装进单一研究循环中，由 FastAPI lifespan 启动后台 scheduler。API 只暴露只读的 latest forecast 与 latest scheduler status，前端通过 typed service 轮询读取结果并重排首页首屏，保留 K 线图、分析原因列表和新闻/情绪模块不变。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Pydantic, LangGraph, Vue 3, TypeScript, Vite, Tailwind CSS, pytest, ruff, npm

---

### Task 1: 定义统一调度与窗口化 forecast 契约

**Files:**
- Create: `src/goldfxgraph/schemas/scheduler.py`
- Modify: `src/goldfxgraph/schemas/forecast.py`
- Modify: `src/goldfxgraph/persistence/models.py`
- Modify: `src/goldfxgraph/persistence/repositories.py`
- Modify: `tests/test_persistence.py`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: 写失败测试，先把新契约钉死**

```python
def test_forecast_result_includes_windowed_direction_contract() -> None:
    bars = _bars()
    forecast = create_research_forecast_from_inputs(
        latest_bar=bars[-1],
        quote=_quote(),
        indicators=compute_technical_indicators(bars),
    )
    assert [item.window_label for item in forecast.window_directions] == ["0-3天", "3-5天", "6-15天", "15天后"]
    assert forecast.window_directions[0].direction in {ForecastDirection.bullish, ForecastDirection.bearish, ForecastDirection.neutral}


async def test_repository_persists_scheduler_status_snapshot() -> None:
    run = await repo.create_scheduler_run(input_summary={"symbol": "XAUUSD"})
    await repo.update_scheduler_run_stage(
        run.id,
        current_stage="agent_technical_analysis",
        agent_statuses=[{"agent": "technical", "status": "running"}],
    )
    loaded = await repo.get_latest_scheduler_run()
    assert loaded is not None
    assert loaded.current_stage == "agent_technical_analysis"
    assert loaded.agent_statuses[0]["status"] == "running"
```

- [ ] **Step 2: 运行定点测试，确认当前实现还没有这些结构**

Run: `pytest tests/test_persistence.py -k scheduler -v && pytest tests/test_workflow.py -k window -v`
Expected: FAIL，原因是 `SchedulerRunModel`、`window_directions` 或 repository 方法尚未实现

- [ ] **Step 3: 实现最小可用的数据结构与持久化边界**

```python
class ForecastWindowDirection(BaseModel):
    window_label: str
    direction: ForecastDirection
    strength: Literal["strong", "moderate", "mild"]
    confidence: float = Field(ge=0, le=1)
    reason: str


class SchedulerRunStatus(BaseModel):
    id: int | None = None
    status: Literal["running", "success", "failed", "skipped"]
    started_at: datetime
    completed_at: datetime | None = None
    current_stage: str
    agent_statuses: list[dict[str, str]] = Field(default_factory=list)
    last_error: str | None = None
```

- [ ] **Step 4: 重新运行测试，确认契约和 ORM 能落地**

Run: `pytest tests/test_persistence.py tests/test_workflow.py -v`
Expected: PASS

- [ ] **Step 5: 提交这个阶段**

```bash
git add src/goldfxgraph/schemas/forecast.py src/goldfxgraph/schemas/scheduler.py src/goldfxgraph/persistence/models.py src/goldfxgraph/persistence/repositories.py tests/test_persistence.py tests/test_workflow.py
git commit -m "feat: add scheduler status and windowed forecast contracts"
```

---

### Task 2: 把统一 15 分钟研究循环接到后端启动路径

**Files:**
- Create: `src/goldfxgraph/research/scheduler.py`
- Modify: `src/goldfxgraph/research/__init__.py`
- Modify: `src/goldfxgraph/api/app.py`
- Modify: `src/goldfxgraph/workflow/nodes.py`
- Modify: `src/goldfxgraph/workflow/graph.py`
- Create: `tests/test_research_scheduler.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: 写失败测试，先证明新的研究调度器还不存在**

```python
@pytest.mark.asyncio
async def test_research_scheduler_emits_stage_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses: list[str] = []

    async def fake_run_forecast_workflow(**kwargs: object) -> object:
        statuses.append("workflow_started")
        return type("Result", (), {"result": object()})()

    scheduler = build_research_scheduler(settings=settings, repository=repository)
    await scheduler.run_once()

    assert statuses == ["workflow_started"]
    assert scheduler.latest_status.current_stage == "persist_result"
```

- [ ] **Step 2: 运行测试，确认当前 app 还在走旧的 EOD maintenance 路径**

Run: `pytest tests/test_research_scheduler.py tests/test_api.py -k startup -v`
Expected: FAIL，原因是 `create_app()` 仍然启动旧的 `run_eod_maintenance` / `start_eod_maintenance_scheduler`

- [ ] **Step 3: 实现新的统一 scheduler，并把 workflow 包装成单一循环**

```python
class ResearchSchedulerHandle:
    stop_event: asyncio.Event
    task: asyncio.Task[None]
    latest_status: SchedulerRunStatus


async def run_research_cycle(*, settings: GoldFXGraphSettings, repository: ForecastRepository, run_id: int) -> None:
    await repository.update_scheduler_run_stage(
        run_id,
        current_stage="tool_fetch_current_gold_quote",
        agent_statuses=[
            {"agent": "technical", "status": "pending"},
            {"agent": "macro", "status": "pending"},
            {"agent": "news", "status": "pending"},
        ],
    )
    await run_forecast_workflow(settings=settings, repository=repository, run_id=run_id)
```

要点：
- scheduler 需要在启动后立即跑一次，然后每 15 分钟再跑一次
- 同一时刻只允许一个 cycle 在跑，下一次 tick 只能等待或跳过
- 每个阶段都要更新 `current_stage`
- `agent_technical_analysis`、`agent_macro_analysis`、`agent_news_analysis`、`agent_risk_analysis`、`agent_forecast_planning` 的状态要能写进 `agent_statuses`

- [ ] **Step 4: 改造 forecast planning，让最终结果写入固定时间窗口方向区间**

```python
def agent_forecast_planning(state: WorkflowState) -> WorkflowState:
    forecast.window_directions = [
        ForecastWindowDirection(
            window_label="0-3天",
            direction=ForecastDirection.bullish,
            strength="moderate",
            confidence=0.64,
            reason="短线动量与价格位置仍偏强",
        ),
        ForecastWindowDirection(
            window_label="3-5天",
            direction=ForecastDirection.bullish,
            strength="strong",
            confidence=0.71,
            reason="若回踩不破关键支撑，延续看多概率更高",
        ),
        ForecastWindowDirection(
            window_label="6-15天",
            direction=ForecastDirection.bullish,
            strength="mild",
            confidence=0.58,
            reason="中期仍偏多，但波动和回撤风险开始抬升",
        ),
        ForecastWindowDirection(
            window_label="15天后",
            direction=ForecastDirection.neutral,
            strength="mild",
            confidence=0.53,
            reason="更远期可能进入震荡整理，需要重新观察宏观与风险事件",
        ),
    ]
```

说明：
- 总方向 `direction` 仍然保留，给首页首屏一个醒目的总判断
- `window_directions` 是对今天之后不同时段的延伸判断，不再单独做“未来 3 天预测”
- `intraday_action`、`entry_price`、`take_profit_price`、`stop_loss_price` 继续保留为结构化字段

- [ ] **Step 5: 改造 app lifespan，用统一 scheduler 替换旧的 EOD 调度启动**

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.settings = resolved_settings
    app.state.repository = ForecastRepository(session_factory)
    scheduler_handle = start_research_scheduler(settings=resolved_settings, repository=app.state.repository)
    app.state.research_scheduler = scheduler_handle
```

要点：
- `run_eod_maintenance` 不再作为启动必经步骤
- `start_eod_maintenance_scheduler()` 不再挂到 app.state
- 启动失败不应该靠“旧的日终维护”去兜底，而是把问题体现在统一调度状态里

- [ ] **Step 6: 重新运行调度器与 app 启动测试**

Run: `pytest tests/test_research_scheduler.py tests/test_api.py -v`
Expected: PASS

- [ ] **Step 7: 提交这个阶段**

```bash
git add src/goldfxgraph/research/scheduler.py src/goldfxgraph/research/__init__.py src/goldfxgraph/api/app.py src/goldfxgraph/workflow/nodes.py src/goldfxgraph/workflow/graph.py tests/test_research_scheduler.py tests/test_api.py
git commit -m "feat: run gold research on unified schedule"
```

---

### Task 3: 收口后端 API，并给前端提供只读状态接口

**Files:**
- Modify: `src/goldfxgraph/api/routes.py`
- Modify: `src/goldfxgraph/schemas/forecast.py`
- Modify: `apps/web/src/types/forecast.ts`
- Modify: `apps/web/src/services/forecastApi.ts`
- Modify: `tests/test_api.py`

- [ ] **Step 1: 写失败测试，先把新 API contract 约束住**

```python
def test_latest_scheduler_status_is_exposed() -> None:
    client = TestClient(create_app(testing=True, repository=cast(ForecastRepository, repository)))
    response = client.get("/api/v1/research-status/latest")
    assert response.status_code in {200, 404}
    assert "agent-key" not in response.text


def test_manual_research_run_endpoint_is_not_exposed() -> None:
    client = TestClient(create_app(testing=True))
    response = client.post("/api/v1/research-runs")
    assert response.status_code in {404, 405}
```

- [ ] **Step 2: 运行测试，确认当前 API 仍然暴露手工触发入口**

Run: `pytest tests/test_api.py -k "research_status or manual_research" -v`
Expected: FAIL，原因是 `/api/v1/research-status/latest` 还没有实现，且 `/api/v1/research-runs` 仍然是可写入口

- [ ] **Step 3: 实现只读 API，并补齐窗口化 forecast 响应**

```python
@router.get("/research-status/latest", response_model=SchedulerStatusResult)
async def get_latest_research_status(request: Request) -> SchedulerStatusResult:
    repository = _repository(request)
    status = await repository.get_latest_scheduler_run()
    if status is None:
        raise ResearchRunNotFoundError()
    return status

@router.get("/forecast/latest", response_model=ForecastResult)
async def get_latest_forecast(request: Request) -> ForecastResult:
    repository = _repository(request)
    forecast = await repository.get_latest_forecast()
    if forecast is None:
        raise ForecastNotFoundError()
    return forecast
```

要点：
- 删除公开的 `POST /api/v1/research-runs`
- `GET /api/v1/research-runs/{run_id}` 保留，只作为历史查询
- `ForecastResult` 需要追加 `window_directions`
- 新增 `SchedulerStatusResult`，把 `started_at`、`completed_at`、`current_stage`、`agent_statuses` 和 `last_error` 一次性返回给前端

- [ ] **Step 4: 更新 typed frontend service**

```ts
export async function fetchLatestResearchStatus(): Promise<ResearchStatusSnapshot | null> {
  const response = await fetch(buildUrl("/api/v1/research-status/latest"), { headers: { Accept: "application/json" } });
  if (response.status === 404 || response.status === 204) {
    return null;
  }
  if (!response.ok) {
    throw new Error("无法加载最新调度状态");
  }
  return (await response.json()) as ResearchStatusSnapshot;
}
```

要点：
- `forecastApi.ts` 不再导出“手工启动研究”的方法
- `types/forecast.ts` 需要补 `WindowDirection`、`ResearchStatusSnapshot` 和 `AgentExecutionStatus`
- 错误态要保留明确的 `404 => empty`、`5xx => error` 语义，不要回退成假数据

- [ ] **Step 5: 重新运行 API 测试并确认 contract 稳定**

Run: `pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 6: 提交这个阶段**

```bash
git add src/goldfxgraph/api/routes.py src/goldfxgraph/schemas/forecast.py apps/web/src/types/forecast.ts apps/web/src/services/forecastApi.ts tests/test_api.py
git commit -m "feat: expose read-only scheduler status api"
```

---

### Task 4: 重排 Dashboard 首屏，并保留 K 线图与新闻/情绪模块

**Files:**
- Modify: `apps/web/src/pages/GoldForecastDashboard.vue`
- Modify: `apps/web/src/constants/forecast.ts`
- Modify: `apps/web/src/styles/main.css`
- Modify: `apps/web/src/App.vue`（如需要补全全局布局，不优先）

- [ ] **Step 1: 写失败测试或最小可运行检查，先证明页面仍然需要重排**

```ts
expect(screen.queryByRole("button", { name: /手动刷新/i })).toBeNull()
expect(screen.getByText(/最新执行时间/)).toBeInTheDocument()
expect(screen.getByText(/0-3天/)).toBeInTheDocument()
```

- [ ] **Step 2: 运行前端定点检查，确认当前页面还没有新的状态区**

Run: `cd apps/web && npm run typecheck`
Expected: FAIL 或至少暴露缺少 `ResearchStatusSnapshot` 类型与状态渲染逻辑

- [ ] **Step 3: 重排首屏信息层级**

要点：
- 第一栏优先显示当前价格、市场方向、固定窗口方向区间、入场/止盈/止损、最新执行时间
- 如果 `research-status/latest` 返回 `running`，首屏要显示每个 agent 的状态 chip
- 删除手动刷新按钮和“点一下再看”的交互
- 保留现有的多 agent 分析原因列表、K 线图、最新市场新闻和情绪模块，位置可以下移，但不能删除

建议结构：

```vue
<section class="hero">
  <div class="price-and-direction">{{ formatPrice(forecast.current_price) }} / {{ directionLabel }}</div>
  <div class="window-directions">
    <ForecastWindowCard v-for="window in forecast.window_directions" :key="window.window_label" :window="window" />
  </div>
  <div class="trade-levels">
    <span>{{ formatPrice(forecast.entry_price) }}</span>
    <span>{{ formatPrice(forecast.take_profit_price) }}</span>
    <span>{{ formatPrice(forecast.stop_loss_price) }}</span>
  </div>
  <div class="scheduler-status">
    <span>{{ latestStatus?.current_stage }}</span>
    <span>{{ formatDateTime(latestStatus?.completed_at ?? latestStatus?.started_at) }}</span>
  </div>
</section>
```

- [ ] **Step 4: 加入自动轮询而不是手动刷新**

```ts
onMounted(() => {
  void refreshDashboard();
  pollingTimer = window.setInterval(() => {
    void refreshDashboard();
  }, 60_000);
});
```

要点：
- 轮询只负责刷新 forecast 和 scheduler status
- 页面不提供用户触发的手动刷新按钮
- 自动轮询的频率可以比 15 分钟更短，用来更快反映“正在执行”状态

- [ ] **Step 5: 更新常量与文案映射**

```ts
export const WINDOW_LABELS: Record<string, string> = {
  "0-3天": "0-3天",
  "3-5天": "3-5天",
  "6-15天": "6-15天",
  "15天后": "15天后",
};
```

要点：
- `bullish` / `bearish` / `neutral` 的中文标签保持一致
- 运行中、成功、失败、等待态要有清晰文案
- 不再出现“手动刷新”或“重新查询”之类暗示用户触发执行的按钮文案

- [ ] **Step 6: 运行前端验证**

Run: `cd apps/web && npm run lint && npm run typecheck && npm run build`
Expected: PASS

- [ ] **Step 7: 提交这个阶段**

```bash
git add apps/web/src/pages/GoldForecastDashboard.vue apps/web/src/constants/forecast.ts apps/web/src/styles/main.css apps/web/src/App.vue
git commit -m "feat: surface scheduler status in dashboard"
```

---

### Task 5: 端到端验证、差异复查与收尾

**Files:**
- Modify: `tests/test_persistence.py`
- Modify: `tests/test_workflow.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_research_scheduler.py`
- Modify: `docs/superpowers/plans/2026-05-27-scheduled-range-forecast-dashboard.md`（如发现计划和实现边界不一致）

- [ ] **Step 1: 跑后端全量相关测试，确认统一调度、窗口化 forecast 和只读 API 同时成立**

Run: `pytest tests/test_persistence.py tests/test_workflow.py tests/test_api.py tests/test_research_scheduler.py -v`
Expected: PASS

- [ ] **Step 2: 跑格式与静态检查**

Run: `ruff check . && ruff format --check . && openspec validate --all`
Expected: PASS

- [ ] **Step 3: 再跑前端构建**

Run: `cd apps/web && npm run lint && npm run typecheck && npm run build`
Expected: PASS

- [ ] **Step 4: 复查 diff，确认没有把无关模块一起改动**

```bash
git diff --stat
git diff -- src/goldfxgraph apps/web tests openspec/changes/scheduled-range-forecast-dashboard docs/superpowers/plans/2026-05-27-scheduled-range-forecast-dashboard.md
```

- [ ] **Step 5: 整理最后一次提交**

```bash
git add src/goldfxgraph apps/web tests openspec/changes/scheduled-range-forecast-dashboard docs/superpowers/plans/2026-05-27-scheduled-range-forecast-dashboard.md
git commit -m "feat: unify gold forecast scheduling and windowed direction output"
```
