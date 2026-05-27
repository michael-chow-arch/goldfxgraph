# TradingView Daily Bar Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 启动时先补齐 XAUUSD completed daily bars，补齐失败直接阻止服务启动，并在运行中跨日继续追平缺口，研究前再做一次强校验，确保整个系统只依赖真实、完整、已完成的日线数据。

**Architecture:**  
补齐逻辑收口到一个共享维护路径：先从数据库读取最新 completed daily bar，再计算当前应已完成的最新交易日，缺口由 TradingView 历史日线提供。应用启动时先执行这条路径，失败就不进入可用状态；运行中的定时维护和 `research-run` 也复用同一条路径，避免出现“启动一套、研究一套、维护一套”的分叉。  
TradingView 历史日线抓取器与实时 quote 分离，前者只负责 completed daily bars 的补齐，后者只负责 current quote。workflow 在取市场数据前先做 freshness preflight，确认 completed daily bars 已追平；若未追平，先补齐，补齐失败则直接返回受控错误，不生成 forecast。

**Tech Stack:** Python、FastAPI、SQLAlchemy、httpx、Pydantic、pytest、Vue 3（仅用于现有前端验证，不改前端功能）

---

### Task 1: TradingView 历史日线抓取与校验

**Files:**
- Create: `src/goldfxgraph/market_data/tradingview_history.py`
- Modify: `src/goldfxgraph/backfill/eod_backfill.py`
- Test: `tests/test_tradingview_history.py`
- Test: `tests/test_backfill.py`

- [ ] **Step 1: Write the failing test**

```python
def test_tradingview_history_parser_returns_only_completed_daily_bars():
    payload = {
        "s": "ok",
        "t": [1779676800, 1779763200],
        "o": [4550.54, 4523.20],
        "h": [4580.21, 4529.10],
        "l": [4548.91, 4510.00],
        "c": [4567.78, 4522.00],
        "v": [115835, 0],
    }

    def handler(request):
        return httpx.Response(200, json=payload, request=request)

    bars = fetch_tradingview_daily_bars(
        start_date=date(2026, 5, 25),
        end_date=date(2026, 5, 26),
        transport=httpx.MockTransport(handler),
    )

    assert len(bars) == 1
    assert bars[0].date.isoformat() == "2026-05-25"
```

预期先失败，因为还没有 TradingView 历史日线解析器。测试要覆盖：
- 能按日期区间请求历史日线
- 只返回合法 completed daily bars
- 跳过未完成或 OHLC 不合法的 bar
- 返回结果按日期升序

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tradingview_history.py -v`
Expected: FAIL，提示找不到模块或解析器未实现。

- [ ] **Step 3: Write minimal implementation**

```python
def fetch_tradingview_daily_bars(
    *,
    start_date: date,
    end_date: date,
    transport: httpx.BaseTransport | None = None,
) -> list[DailyBar]:
    # 1. 请求 TradingView 历史接口或页面内嵌历史数据
    # 2. 解析出日期、open/high/low/close/volume
    # 3. 丢弃未完成、缺字段或 OHLC 不合法的 bar
    # 4. 按日期升序返回 completed daily bars
```

实现要求：
- 只接受 TradingView 返回的 completed daily bars
- 不允许写入当前未完成日线
- 不允许把 OHLC 不合法的数据写成 bar
- 不允许 fallback 到 Yahoo

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tradingview_history.py tests/test_backfill.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/goldfxgraph/market_data/tradingview_history.py src/goldfxgraph/backfill/eod_backfill.py tests/test_tradingview_history.py tests/test_backfill.py
git commit -m "feat: add TradingView daily bar history fetcher"
```

### Task 2: 启动必补齐与运行中跨日补齐

**Files:**
- Modify: `src/goldfxgraph/backfill/maintenance.py`
- Modify: `src/goldfxgraph/backfill/scheduler.py`
- Modify: `src/goldfxgraph/api/app.py`
- Modify: `src/goldfxgraph/backfill/cli.py`
- Modify: `src/goldfxgraph/backfill/eod_backfill.py`
- Test: `tests/test_maintenance_scheduler.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_startup_fails_when_daily_bar_backfill_fails():
    settings = GoldFXGraphSettings(
        xauusd_csv_path=Path("data/raw/xauusd_daily.csv"),
        database_url="sqlite+aiosqlite:///:memory:",
        eod_backfill_timezone="America/New_York",
        eod_backfill_cutoff_hour=17,
        eod_backfill_cutoff_minute=0,
    )
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = ForecastRepository(session_factory)
    await repository.upsert_market_bars(
        [
            DailyBar(
                date=date(2026, 5, 22),
                open=4520.0,
                high=4530.0,
                low=4510.0,
                close=4521.0,
                source="TradingView",
                symbol="XAUUSD",
            )
        ]
    )
    monkeypatch.setattr(
        "goldfxgraph.backfill.eod_backfill.fetch_tradingview_daily_bars",
        lambda **kwargs: [],
    )
    with pytest.raises(RuntimeError, match="daily bar backfill"):
        await run_eod_maintenance(
            settings=settings,
            repository=repository,
            now=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
        )
```

再补一个跨日缺口测试：

```python
async def test_run_eod_backfill_fills_missing_trading_days_from_tradingview():
    settings = GoldFXGraphSettings(
        xauusd_csv_path=Path("data/raw/xauusd_daily.csv"),
        database_url="sqlite+aiosqlite:///:memory:",
        eod_backfill_timezone="America/New_York",
        eod_backfill_cutoff_hour=17,
        eod_backfill_cutoff_minute=0,
    )
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = ForecastRepository(session_factory)
    await repository.upsert_market_bars(
        [
            DailyBar(
                date=date(2026, 5, 22),
                open=4520.0,
                high=4530.0,
                low=4510.0,
                close=4521.0,
                source="TradingView",
                symbol="XAUUSD",
            )
        ]
    )
    monkeypatch.setattr(
        "goldfxgraph.backfill.eod_backfill.fetch_tradingview_daily_bars",
        lambda **kwargs: [
            DailyBar(
                date=date(2026, 5, 23),
                open=4532.0,
                high=4582.6,
                low=4531.3,
                close=4523.2,
                source="TradingView",
                symbol="XAUUSD",
            ),
        ],
    )
    result = await run_eod_backfill(
        settings=settings,
        repository=repository,
        now=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
    )
    assert result.written is True
    assert result.appended_dates == [date(2026, 5, 23)]
```

测试要覆盖：
- 启动时发现缺口会先补齐
- 补齐失败时应用启动失败
- 运行中跨日后会补齐中间缺失交易日
- 没有缺口时返回 no-op

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_maintenance_scheduler.py tests/test_api.py -v`
Expected: FAIL，说明当前 startup 没有强制补齐或缺少 TradingView 历史补齐逻辑。

- [ ] **Step 3: Write minimal implementation**

```python
async def run_eod_maintenance(
    *,
    settings: GoldFXGraphSettings,
    repository: ForecastRepository,
    now: datetime | None = None,
) -> EodMaintenanceResult:
    # 1. 计算 current time 对应的 latest completed trading day
    # 2. 对照数据库最新 completed daily bar 计算缺口
    # 3. 通过 TradingView 补齐缺口
    # 4. 缺口无法补齐时抛出受控错误
```

实现要求：
- 启动时先执行补齐，失败就抛错
- 定时任务和手动 maintenance 复用同一套补齐逻辑
- 维护日志明确区分 `written`、`no-op`、`failed`
- 不允许继续保留 Yahoo 作为补齐回退

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_maintenance_scheduler.py tests/test_api.py tests/test_backfill.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/goldfxgraph/backfill/maintenance.py src/goldfxgraph/backfill/scheduler.py src/goldfxgraph/api/app.py src/goldfxgraph/backfill/cli.py src/goldfxgraph/backfill/eod_backfill.py tests/test_maintenance_scheduler.py tests/test_api.py
git commit -m "feat: enforce startup daily bar backfill"
```

### Task 3: 研究前强校验

**Files:**
- Modify: `src/goldfxgraph/workflow/nodes.py`
- Modify: `src/goldfxgraph/workflow/graph.py`
- Modify: `src/goldfxgraph/research/cli.py`
- Test: `tests/test_workflow.py`
- Test: `tests/test_research_cli.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_workflow_refuses_to_run_when_daily_bars_are_stale():
    state = WorkflowState(
        settings=GoldFXGraphSettings(
            xauusd_csv_path=Path("data/raw/xauusd_daily.csv"),
            database_url="sqlite+aiosqlite:///:memory:",
            eod_backfill_timezone="America/New_York",
            eod_backfill_cutoff_hour=17,
            eod_backfill_cutoff_minute=0,
        ),
        repository=ForecastRepository(create_session_factory("sqlite+aiosqlite:///:memory:")),
        run_id=1,
    )
    monkeypatch.setattr(
        "goldfxgraph.workflow.nodes.run_eod_maintenance",
        lambda **kwargs: pytest.fail("workflow should not proceed with stale market data"),
    )
    with pytest.raises(QuoteProviderError, match="market data freshness"):
        graph = build_forecast_graph().compile()
        await graph.ainvoke(state)
```

再补一个研究前自动追平测试：

```python
async def test_research_run_triggers_daily_bar_freshness_preflight():
    state = WorkflowState(
        settings=GoldFXGraphSettings(
            xauusd_csv_path=Path("data/raw/xauusd_daily.csv"),
            database_url="sqlite+aiosqlite:///:memory:",
            eod_backfill_timezone="America/New_York",
            eod_backfill_cutoff_hour=17,
            eod_backfill_cutoff_minute=0,
        ),
        repository=ForecastRepository(create_session_factory("sqlite+aiosqlite:///:memory:")),
        run_id=1,
    )
    monkeypatch.setattr(
        "goldfxgraph.workflow.nodes.run_eod_maintenance",
        lambda **kwargs: None,
    )
    graph = build_forecast_graph().compile()
    result = await graph.ainvoke(state)
    assert result["result"] is not None
```

测试要覆盖：
- completed daily bars 未追平时，workflow 不继续做技术/宏观/新闻分析
- 日线追平时，workflow 正常继续
- `research-run` 触发的路径也会先做 freshness preflight

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workflow.py tests/test_research_cli.py -v`
Expected: FAIL，说明当前 workflow 还没有在研究前做日线强校验。

- [ ] **Step 3: Write minimal implementation**

```python
async def ensure_market_data_freshness(
    *,
    settings: GoldFXGraphSettings,
    repository: ForecastRepository,
    now: datetime,
) -> None:
    # 1. 计算当前应完成的 trading day
    # 2. 若数据库未追平，调用 maintenance/backfill
    # 3. 若补齐失败，抛出受控错误，中止 workflow
```

实现要求：
- 在 `tool_load_market_data` 前先检查 completed daily bars 是否追平
- 未追平时先走补齐
- 补齐失败时返回受控错误，不进入 agent 分析
- 研究结果不得使用旧 bar 冒充最新数据

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_workflow.py tests/test_research_cli.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/goldfxgraph/workflow/nodes.py src/goldfxgraph/workflow/graph.py src/goldfxgraph/research/cli.py tests/test_workflow.py tests/test_research_cli.py
git commit -m "feat: add market data freshness preflight"
```

### Task 4: 端到端验证与旧路径清理

**Files:**
- Modify: `src/goldfxgraph/market_data/yahoo_history.py`
- Modify: `src/goldfxgraph/backfill/eod_backfill.py`
- Modify: `src/goldfxgraph/market_data/__init__.py`
- Modify: `src/goldfxgraph/backfill/__init__.py`
- Test: `tests/test_market_data.py`
- Test: `tests/test_backfill.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_yahoo_history_is_no_longer_used_for_daily_bar_backfill():
    settings = GoldFXGraphSettings(
        xauusd_csv_path=Path("data/raw/xauusd_daily.csv"),
        database_url="sqlite+aiosqlite:///:memory:",
        eod_backfill_timezone="America/New_York",
        eod_backfill_cutoff_hour=17,
        eod_backfill_cutoff_minute=0,
    )
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = ForecastRepository(session_factory)
    await repository.upsert_market_bars(
        [
            DailyBar(
                date=date(2026, 5, 22),
                open=4520.0,
                high=4530.0,
                low=4510.0,
                close=4521.0,
                source="TradingView",
                symbol="XAUUSD",
            )
        ]
    )
    monkeypatch.setattr(
        "goldfxgraph.backfill.eod_backfill.fetch_gold_daily_bars",
        lambda **kwargs: pytest.fail("Yahoo history should not be called for daily bar backfill"),
    )
    monkeypatch.setattr(
        "goldfxgraph.backfill.eod_backfill.fetch_tradingview_daily_bars",
        lambda **kwargs: [],
    )
    result = await run_eod_backfill(
        settings=settings,
        repository=repository,
        now=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
    )
    assert result.written is False
```

再补一个端到端补齐断言：

```python
async def test_startup_and_maintenance_use_tradingview_for_gap_fill():
    settings = GoldFXGraphSettings(
        xauusd_csv_path=Path("data/raw/xauusd_daily.csv"),
        database_url="sqlite+aiosqlite:///:memory:",
        eod_backfill_timezone="America/New_York",
        eod_backfill_cutoff_hour=17,
        eod_backfill_cutoff_minute=0,
    )
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = ForecastRepository(session_factory)
    await repository.upsert_market_bars(
        [
            DailyBar(
                date=date(2026, 5, 22),
                open=4520.0,
                high=4530.0,
                low=4510.0,
                close=4521.0,
                source="TradingView",
                symbol="XAUUSD",
            )
        ]
    )
    monkeypatch.setattr(
        "goldfxgraph.backfill.eod_backfill.fetch_tradingview_daily_bars",
        lambda **kwargs: [
            DailyBar(
                date=date(2026, 5, 23),
                open=4532.0,
                high=4582.6,
                low=4531.3,
                close=4523.2,
                source="TradingView",
                symbol="XAUUSD",
            ),
        ],
    )
    result = await run_eod_backfill(
        settings=settings,
        repository=repository,
        now=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
    )
    assert result.appended_dates == [date(2026, 5, 23)]
```

测试要覆盖：
- daily bar 补齐不再依赖 Yahoo
- 只要 TradingView 给不出合法 completed daily bar，就不会写假数据
- 端到端维护结果在缺口修复后返回 current/no-op

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_market_data.py tests/test_backfill.py -v`
Expected: FAIL，说明旧的 Yahoo 路径还在被测试覆盖。

- [ ] **Step 3: Write minimal implementation**

```python
def fetch_gold_daily_bars(
    *,
    start_date: date,
    end_date: date,
    transport: httpx.BaseTransport | None = None,
) -> list[DailyBar]:
    # 1. 如果历史补齐已经切到 TradingView，这里应当不再承担 daily bar 补齐职责
    # 2. 保留该函数仅作兼容过渡时，应确保 backfill 不再引用它
    # 3. 最终应从调用链中移除 Yahoo 历史补齐入口
```

实现要求：
- 将历史日线补齐路径统一迁移到 TradingView
- 清理补齐链路中的 Yahoo fallback
- 保留数据库中的真实历史记录，不回写任何推测值

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_market_data.py tests/test_backfill.py tests/test_workflow.py tests/test_research_cli.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/goldfxgraph/market_data/yahoo_history.py src/goldfxgraph/backfill/eod_backfill.py src/goldfxgraph/market_data/__init__.py src/goldfxgraph/backfill/__init__.py tests/test_market_data.py tests/test_backfill.py
git commit -m "feat: remove yahoo fallback from daily bar backfill"
```
