# TradingView Only Realtime Quote Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 GoldFXGraph 的实时 XAUUSD quote 彻底收口到 TradingView 页面数据，删除 Gold API 的运行时 fallback，并让后端、health check、API 与前端都一致展示真实来源与明确失败状态。

**Architecture:** 新增一个专用的 TradingView 实时报价解析层，`CurrentQuoteProvider` 不再携带 Gold API 默认候选。workflow 的 `tool_fetch_current_gold_quote`、agent health check 和 research-run 统一依赖同一条 TradingView quote 线路；API 与前端只消费结构化 `CurrentQuote`，不再暴露旧源名称。历史 completed daily bars 保持原有边界不变，实时 quote 失败时显式返回 unavailable 或结构化错误，避免任何“看起来像最新”的伪值。

**Tech Stack:** Python 3.13, FastAPI, Pydantic, httpx, LangGraph, Vue 3, TypeScript, Vite, Tailwind CSS, pytest, ruff, npm

---

### Task 1: 实现 TradingView-only 实时报价 provider

**Files:**
- Modify: `src/goldfxgraph/market_data/current_quote.py`
- Create: `src/goldfxgraph/market_data/tradingview_quote.py`
- Modify: `tests/test_market_data.py`
- Create: `tests/fixtures/tradingview_xauusd_page.html`
- Create: `tests/fixtures/tradingview_xauusd_page_broken.html`

- [ ] 1.1 写一个失败测试，证明当前 provider 仍会尝试 Gold API 默认候选 URL，作为重构前的基线

```python
def test_current_quote_provider_does_not_use_gold_api_as_runtime_fallback(monkeypatch):
    provider = CurrentQuoteProvider(url=None, candidate_urls=None)
    assert "api.gold-api.com" not in provider.fetch.__code__.co_consts
```

- [ ] 1.2 运行失败测试，确认当前实现仍然会触发旧候选路径

Run: `pytest tests/test_market_data.py -k current_quote_provider -v`
Expected: FAIL 或至少暴露 Gold API 默认候选仍存在

- [ ] 1.3 新增 `TradingViewQuoteProvider`，只从 `https://www.tradingview.com/symbols/XAUUSD/` 解析实时价格、来源和时间戳，并把失败显式转换为 `QuoteProviderError`

```python
class TradingViewQuoteProvider:
    def __init__(self, url: str = "https://www.tradingview.com/symbols/XAUUSD/", transport: httpx.BaseTransport | None = None) -> None:
        self.url = url
        self.transport = transport

    def fetch(self) -> CurrentQuote:
        ...
```

- [ ] 1.4 修改 `CurrentQuoteProvider`，删除 `DEFAULT_CANDIDATE_URLS` 的 Gold API 条目，并把 `fetch()` 改成只依赖 TradingView provider

```python
def fetch(self) -> CurrentQuote:
    provider = TradingViewQuoteProvider(url=self.url, transport=self.transport)
    return provider.fetch()
```

- [ ] 1.5 补充 TradingView HTML fixture 测试，覆盖成功解析、页面结构变化和网络失败三种情况，确保不会回退到旧源或伪造数据

```python
def test_tradingview_quote_provider_parses_success_fixture():
    ...
    assert quote.symbol == "XAUUSD"
    assert quote.current_price > 0
    assert "tradingview" in quote.data_source.lower()
```

- [ ] 1.6 运行 quote provider 测试，确认 TradingView-only provider 通过、旧 Gold API fallback 被移除

Run: `pytest tests/test_market_data.py -v`
Expected: PASS

### Task 2: 把 workflow、health check 与 API 全部切到同一条 TradingView quote 线路

**Files:**
- Modify: `src/goldfxgraph/workflow/nodes.py`
- Modify: `src/goldfxgraph/diagnostics/agent_health.py`
- Modify: `src/goldfxgraph/api/routes.py`
- Modify: `src/goldfxgraph/api/app.py`
- Modify: `src/goldfxgraph/schemas/forecast.py`
- Modify: `tests/test_workflow.py`
- Modify: `tests/test_diagnostics.py`
- Modify: `tests/test_api.py`

- [ ] 2.1 写一个失败测试，验证 `tool_fetch_current_gold_quote` 不再从 Gold API 候选 URL 取值，而是只依赖 TradingView provider

```python
def test_tool_fetch_current_gold_quote_uses_tradingview_only(monkeypatch):
    ...
    assert quote.data_source.startswith("tradingview")
```

- [ ] 2.2 写一个失败测试，验证 health check 在 quote 不可用时会显式报告 unavailable/错误，而不是偷偷用 `latest_market_bar_close` 冒充实时数据

```python
def test_agent_health_check_reports_tradingview_quote_failure(monkeypatch):
    ...
    assert report.quote_source != "latest_market_bar_close"
```

- [ ] 2.3 修改 `tool_fetch_current_gold_quote`，让其只调用 TradingView 实时报价 provider，并把失败原样传到 workflow state

```python
def tool_fetch_current_gold_quote(state: WorkflowState) -> WorkflowState:
    provider = TradingViewQuoteProvider(...)
    quote = provider.fetch()
    return {**state, "quote": quote}
```

- [ ] 2.4 修改 `run_agent_health_check()`，删除 `QuoteProviderError` 的历史 bar 假回退逻辑，让 quote 失败时明确进入 `quote_warning` 和 fail probe 状态

```python
except QuoteProviderError as exc:
    quote_warning = str(exc).strip() or "TradingView quote provider failed"
    state = {**state, "quote_warning": quote_warning}
```

- [ ] 2.5 修改 API forecast contract 的来源语义，让 `data_source`、`quote_source` 和前端输出统一反映 TradingView，不再展示 Gold API

```python
class CurrentQuote(BaseModel):
    data_source: str
    data_timestamp: datetime
```

- [ ] 2.6 运行 workflow / diagnostics / API 测试，确认 research-run、health check 和 latest forecast 都能正确展示 TradingView 来源与显式失败

Run: `pytest tests/test_workflow.py tests/test_diagnostics.py tests/test_api.py -v`
Expected: PASS

### Task 3: 前端统一展示 TradingView 来源和明确的 unavailable 状态

**Files:**
- Modify: `apps/web/src/services/forecastApi.ts`
- Modify: `apps/web/src/types/forecast.ts`
- Modify: `apps/web/src/constants/forecast.ts`
- Modify: `apps/web/src/pages/GoldForecastDashboard.vue`
- Modify: `apps/web/src/styles/main.css`
- Modify: `tests/test_api.py`（如前端用例需要同步调整 API fixture）

- [ ] 3.1 写一个前端类型/数据转换测试思路，确认 `data_source` 只会显示 TradingView 文案，不会再出现 Gold API 字符串

```ts
expect(formatDataSource("tradingview.com")).toContain("TradingView")
expect(formatDataSource("api.gold-api.com")).not.toContain("Gold API")
```

- [ ] 3.2 修改 `forecastApi.ts` 和 `types/forecast.ts`，确保前端读取的实时 quote 源字段与后端一致，并且为空或失败时有显式状态

```ts
export interface CurrentQuote {
  dataSource: string;
  dataTimestamp: string;
}
```

- [ ] 3.3 修改 `GoldForecastDashboard.vue`，把实时价格快照、数据来源、错误/空态文案统一为 TradingView-only 语义，去掉任何旧源展示

```vue
<span class="text-xs text-slate-400">实时来源：TradingView / XAUUSD</span>
```

- [ ] 3.4 调整 `forecast.ts` 常量或映射，确保方向、来源、失败状态都不会显示 Gold API 的残留文案

- [ ] 3.5 运行前端类型检查与构建，确认页面在成功、空态和错误态都不会显示旧源名称

Run: `cd apps/web && npm run typecheck && npm run build`
Expected: PASS

### Task 4: 端到端回归与旧源清理

**Files:**
- Modify: `README.md`（如果运行时来源说明仍提到 Gold API fallback）
- Modify: `.env.example`（如果有旧实时 quote 配置说明）
- Modify: `src/goldfxgraph/market_data/__init__.py`（如需要更新导出）
- Modify: `src/goldfxgraph/market_data/current_quote.py`
- Modify: `src/goldfxgraph/packages/common/settings.py`
- Modify: `tests/test_settings.py`
- Modify: `tests/test_openai_client.py`（如需调整误报或配置文案）

- [ ] 4.1 复查配置与文档，删除所有把 Gold API 描述成 runtime 实时报价来源的说明，保留历史说明时必须明确标注为非运行时链路

- [ ] 4.2 运行后端全量相关测试，确认 quote provider、workflow、health check、API 和 persistence 都不会把旧源误展示为最新

Run: `pytest tests/test_market_data.py tests/test_workflow.py tests/test_diagnostics.py tests/test_api.py tests/test_settings.py -v`
Expected: PASS

- [ ] 4.3 运行前端全量检查，确认 dashboard 只显示 TradingView 来源和显式失败/空态

Run: `cd apps/web && npm run typecheck && npm run build`
Expected: PASS

- [ ] 4.4 检查 `git diff`，确认只包含 TradingView-only realtime quote 相关改动，没有把其他历史脏改动卷入本次实现

```bash
git diff --stat
git diff -- openspec/changes/tradingview-only-realtime-quote src/goldfxgraph apps/web tests
```

- [ ] 4.5 提交本次实现，使用清晰的 commit message，例如 `feat: switch realtime quote to tradingview only`

```bash
git add src/goldfxgraph apps/web tests openspec/changes/tradingview-only-realtime-quote docs/superpowers/specs/2026-05-26-tradingview-only-realtime-quote-design.md
git commit -m "feat: switch realtime quote to tradingview only"
```
