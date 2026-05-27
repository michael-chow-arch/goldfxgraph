# Bootstrap Fullstack XAUUSD Forecast Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 GoldFXGraph 第一版端到端黄金预测研究流程：FastAPI + 真实 XAUUSD 数据 + LangGraph 多 Agent + PostgreSQL + Vue 3/Tailwind Dashboard。

**Architecture:** 后端采用清晰分层：settings/schema/data/indicator/workflow/persistence/api；workflow 使用显式 LangGraph 节点，tool 节点做确定性工作，agent 节点输出结构化摘要。前端位于 `apps/web/`，通过 typed service 调用 `/api/v1`，Dashboard 只展示 API 返回的数据和明确状态。

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pandas, httpx, LangGraph, SQLAlchemy async, asyncpg, pytest, ruff, pyright, Vue 3, TypeScript, Vite, Tailwind CSS.

---

## File Structure

- Create `src/goldfxgraph/__init__.py`: 后端包标记。
- Create `src/goldfxgraph/api/app.py`: FastAPI app factory。
- Create `src/goldfxgraph/api/routes.py`: `/api/v1` router 和 endpoint。
- Create `src/goldfxgraph/api/errors.py`: API 错误类型和 HTTP 映射。
- Create `src/goldfxgraph/schemas/forecast.py`: Pydantic forecast、quote、daily bar、agent summary、run models。
- Create `src/goldfxgraph/market_data/csv_loader.py`: XAUUSD CSV 读取与校验。
- Create `src/goldfxgraph/market_data/current_quote.py`: current/latest quote provider。
- Create `src/goldfxgraph/indicators/technical.py`: 基础技术指标。
- Create `src/goldfxgraph/workflow/graph.py`: LangGraph 图构建与节点名注册。
- Create `src/goldfxgraph/workflow/nodes.py`: router/tool/agent 节点实现。
- Create `src/goldfxgraph/persistence/database.py`: async engine/session/metadata 初始化。
- Create `src/goldfxgraph/persistence/models.py`: `ResearchRunModel`、`ForecastModel`。
- Create `src/goldfxgraph/persistence/repositories.py`: research run 和 forecast repository。
- Create `src/goldfxgraph/packages/common/settings.py`: 环境配置加载。
- Modify `pyproject.toml`: 添加 FastAPI、uvicorn、aiosqlite 测试依赖（如需要）。
- Create `.env.example` and `dev.env`: 非敏感配置样例。
- Create `tests/`: 后端测试文件。
- Create `apps/web/`: Vue 3 + Vite + Tailwind 前端项目。
- Modify `openspec/changes/bootstrap-fullstack-xauusd-forecast-dashboard/tasks.md`: 实现后勾选完成项。

---

### Task 1: Backend Configuration And Package Skeleton

**Files:**
- Create: `src/goldfxgraph/__init__.py`
- Create: `src/goldfxgraph/packages/__init__.py`
- Create: `src/goldfxgraph/packages/common/__init__.py`
- Create: `src/goldfxgraph/packages/common/settings.py`
- Modify: `pyproject.toml`
- Create: `.env.example`
- Create: `dev.env`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write failing settings tests**

Create `tests/test_settings.py`:

```python
from pathlib import Path

from goldfxgraph.packages.common.settings import GoldFXGraphSettings, load_settings


def test_settings_loads_from_explicit_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / "dev.env"
    env_file.write_text(
        "\n".join(
            [
                "GOLDFXGRAPH_ENV=local",
                "GOLDFXGRAPH_LOG_LEVEL=DEBUG",
                "GOLDFXGRAPH_DATABASE_URL=postgresql+asyncpg://u:p@localhost:5432/db",
                "GOLDFXGRAPH_XAUUSD_CSV_PATH=data/raw/xauusd_d.csv",
                "GOLDFXGRAPH_CURRENT_QUOTE_URL=https://example.test/quote",
                "GOLDFXGRAPH_CURRENT_QUOTE_API_KEY=quote-key",
                "GOLDFXGRAPH_AGENT_API_BASE_URL=https://agent.example.test/v1",
                "GOLDFXGRAPH_AGENT_API_KEY=agent-key",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)

    assert settings.env == "local"
    assert settings.log_level == "DEBUG"
    assert str(settings.xauusd_csv_path) == "data/raw/xauusd_d.csv"
    assert settings.agent_api_base_url == "https://agent.example.test/v1"
    assert settings.agent_api_key.get_secret_value() == "agent-key"


def test_settings_repr_does_not_expose_agent_key() -> None:
    settings = GoldFXGraphSettings(
        agent_api_key="super-secret",
        current_quote_api_key="quote-secret",
    )

    rendered = repr(settings)

    assert "super-secret" not in rendered
    assert "quote-secret" not in rendered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_settings.py -q`

Expected: FAIL with `ModuleNotFoundError` or missing settings symbols.

- [ ] **Step 3: Add dependencies and settings implementation**

Modify `pyproject.toml` dependencies to include:

```toml
"fastapi>=0.124.0",
"uvicorn[standard]>=0.38.0",
```

Create `src/goldfxgraph/packages/common/settings.py`:

```python
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class GoldFXGraphSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GOLDFXGRAPH_", extra="ignore")

    env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://goldfxgraph:change_me@localhost:5432/goldfxgraph"
    xauusd_csv_path: Path = Path("data/raw/xauusd_daily.csv")
    current_quote_url: str | None = None
    current_quote_api_key: SecretStr | None = None
    agent_api_base_url: str | None = None
    agent_api_key: SecretStr | None = None


def _load_env_file_values(env_file: Path | None) -> dict[str, str]:
    if env_file is None or not env_file.exists():
        return {}
    raw_values = dotenv_values(env_file)
    prefix = "GOLDFXGRAPH_"
    return {
        key.removeprefix(prefix).lower(): value
        for key, value in raw_values.items()
        if key.startswith(prefix) and value is not None
    }


def load_settings(env_file: Path | str | None = Path("dev.env")) -> GoldFXGraphSettings:
    path = Path(env_file) if env_file is not None else None
    return GoldFXGraphSettings(**_load_env_file_values(path))


@lru_cache
def get_settings() -> GoldFXGraphSettings:
    return load_settings()
```

Also add `pydantic-settings>=2.12.0` to `pyproject.toml`.

- [ ] **Step 4: Add safe env samples**

Create `.env.example`:

```env
GOLDFXGRAPH_ENV=local
GOLDFXGRAPH_LOG_LEVEL=INFO
GOLDFXGRAPH_DATABASE_URL=postgresql+asyncpg://goldfxgraph:change_me@localhost:5432/goldfxgraph
GOLDFXGRAPH_XAUUSD_CSV_PATH=data/raw/xauusd_daily.csv
GOLDFXGRAPH_CURRENT_QUOTE_URL=
GOLDFXGRAPH_CURRENT_QUOTE_API_KEY=change_me
GOLDFXGRAPH_AGENT_API_BASE_URL=http://localhost:11434/v1
GOLDFXGRAPH_AGENT_API_KEY=change_me
VITE_API_BASE_URL=http://localhost:8000
```

Create `dev.env` with the same non-secret placeholder values, using `data/raw/xauusd_d.csv` so the existing repository CSV works locally.

- [ ] **Step 5: Run tests and checks**

Run: `pytest tests/test_settings.py -q`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS or only import-order issues that are fixed before proceeding.

---

### Task 2: Forecast Schemas, CSV Loader, Quote Provider, And Indicators

**Files:**
- Create: `src/goldfxgraph/schemas/__init__.py`
- Create: `src/goldfxgraph/schemas/forecast.py`
- Create: `src/goldfxgraph/market_data/__init__.py`
- Create: `src/goldfxgraph/market_data/csv_loader.py`
- Create: `src/goldfxgraph/market_data/current_quote.py`
- Create: `src/goldfxgraph/indicators/__init__.py`
- Create: `src/goldfxgraph/indicators/technical.py`
- Test: `tests/test_market_data.py`
- Test: `tests/test_indicators.py`

- [ ] **Step 1: Write failing data and indicator tests**

Create `tests/test_market_data.py`:

```python
from pathlib import Path

import pytest

from goldfxgraph.market_data.csv_loader import CsvValidationError, load_xauusd_daily_csv
from goldfxgraph.market_data.current_quote import CurrentQuoteProvider, QuoteProviderError


def test_load_xauusd_daily_csv_sorts_and_preserves_optional_fields(tmp_path: Path) -> None:
    csv_path = tmp_path / "xauusd.csv"
    csv_path.write_text(
        "Date,Open,High,Low,Close,Volume,Source,Symbol\n"
        "2024-01-02,2050,2060,2040,2055,10,unit,XAUUSD\n"
        "2024-01-01,2040,2050,2030,2045,9,unit,XAUUSD\n",
        encoding="utf-8",
    )

    result = load_xauusd_daily_csv(csv_path)

    assert result.latest_bar.date.isoformat() == "2024-01-02"
    assert result.latest_bar.close == 2055
    assert result.latest_bar.source == "unit"
    assert result.latest_bar.symbol == "XAUUSD"
    assert len(result.bars) == 2


def test_load_repository_csv_fixture() -> None:
    result = load_xauusd_daily_csv(Path("data/raw/xauusd_d.csv"))

    assert result.latest_bar.close > 0
    assert result.bars[0].date <= result.latest_bar.date


def test_load_xauusd_daily_csv_rejects_missing_required_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("Date,Open,High,Close\n2024-01-01,1,2,3\n", encoding="utf-8")

    with pytest.raises(CsvValidationError, match="low"):
        load_xauusd_daily_csv(csv_path)


def test_quote_provider_requires_configured_url() -> None:
    provider = CurrentQuoteProvider(url=None, api_key=None)

    with pytest.raises(QuoteProviderError, match="not configured"):
        provider.fetch()
```

Create `tests/test_indicators.py`:

```python
from datetime import date

from goldfxgraph.indicators.technical import compute_technical_indicators
from goldfxgraph.schemas.forecast import DailyBar


def _bar(day: int, close: float) -> DailyBar:
    return DailyBar(date=date(2024, 1, day), open=close - 1, high=close + 2, low=close - 2, close=close)


def test_compute_technical_indicators_returns_deterministic_values() -> None:
    bars = [_bar(day, 1900 + day) for day in range(1, 31)]

    indicators = compute_technical_indicators(bars)

    assert indicators.sma_20 == 1910.5 + 10
    assert indicators.ema_12 is not None
    assert indicators.rsi_14 is not None
    assert indicators.atr_14 is not None


def test_compute_technical_indicators_marks_unavailable_values() -> None:
    indicators = compute_technical_indicators([_bar(1, 1901)])

    assert indicators.sma_20 is None
    assert "sma_20" in indicators.unavailable
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_market_data.py tests/test_indicators.py -q`

Expected: FAIL with missing modules.

- [ ] **Step 3: Implement Pydantic schemas**

Create `src/goldfxgraph/schemas/forecast.py` with enums and models:

```python
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ForecastDirection(StrEnum):
    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"


class DailyBar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    source: str | None = None
    symbol: str = "XAUUSD"


class MarketDataSet(BaseModel):
    symbol: str = "XAUUSD"
    bars: list[DailyBar]
    latest_bar: DailyBar


class CurrentQuote(BaseModel):
    symbol: str = "XAUUSD"
    current_price: float
    data_source: str
    data_timestamp: datetime


class TechnicalIndicators(BaseModel):
    sma_20: float | None = None
    ema_12: float | None = None
    rsi_14: float | None = None
    atr_14: float | None = None
    unavailable: dict[str, str] = Field(default_factory=dict)


class AgentVote(BaseModel):
    agent: str
    direction: ForecastDirection
    confidence: float = Field(ge=0, le=1)
    rationale: str


class ForecastResult(BaseModel):
    id: int | None = None
    run_id: int | None = None
    symbol: str = "XAUUSD"
    reference_time: datetime
    data_timestamp: datetime
    data_source: str
    current_price: float
    daily_open: float
    daily_high: float
    daily_low: float
    daily_close: float
    direction: ForecastDirection
    entry_price: float
    take_profit_price: float
    stop_loss_price: float
    holding_period: str
    intraday_action: str
    long_term_action: str
    confidence_score: float = Field(ge=0, le=1)
    technical_summary: str
    macro_summary: str
    news_summary: str
    risk_summary: str
    agent_votes: list[AgentVote]
    risk_notes: list[str]
    disclaimer: str = "本结果仅用于研究和决策支持，不构成金融建议或交易指令。"


class ResearchRunResult(BaseModel):
    id: int | None = None
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    input_summary: dict[str, object] = Field(default_factory=dict)
    error_message: str | None = None
    forecast: ForecastResult | None = None
```

- [ ] **Step 4: Implement CSV loader and quote provider**

Implement `load_xauusd_daily_csv(path: Path) -> MarketDataSet` using pandas, normalizing columns to lowercase, validating required columns, sorting by `date`, and preserving optional fields.

Implement `CurrentQuoteProvider.fetch()` with `httpx.get`, expecting JSON containing one of `price/current_price/close` and optional `source/timestamp`; raise `QuoteProviderError` if URL is missing, response fails, or price is absent.

- [ ] **Step 5: Implement technical indicators**

Implement `compute_technical_indicators(bars: Sequence[DailyBar]) -> TechnicalIndicators` with deterministic pandas calculations for SMA-20, EMA-12, RSI-14, ATR-14. For insufficient data, set the value to `None` and add a Chinese reason in `unavailable`.

- [ ] **Step 6: Run tests and fix exact failures**

Run: `pytest tests/test_market_data.py tests/test_indicators.py -q`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS.

---

### Task 3: Persistence Layer

**Files:**
- Create: `src/goldfxgraph/persistence/__init__.py`
- Create: `src/goldfxgraph/persistence/database.py`
- Create: `src/goldfxgraph/persistence/models.py`
- Create: `src/goldfxgraph/persistence/repositories.py`
- Test: `tests/test_persistence.py`

- [ ] **Step 1: Write failing persistence tests**

Create `tests/test_persistence.py` using `sqlite+aiosqlite` for fast repository tests while keeping production URL PostgreSQL:

```python
import pytest

from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import ForecastDirection, ForecastResult


pytestmark = pytest.mark.asyncio


def _forecast() -> ForecastResult:
    from datetime import datetime, timezone
    from goldfxgraph.schemas.forecast import AgentVote

    now = datetime.now(timezone.utc)
    return ForecastResult(
        reference_time=now,
        data_timestamp=now,
        data_source="unit",
        current_price=2050,
        daily_open=2040,
        daily_high=2060,
        daily_low=2035,
        daily_close=2048,
        direction=ForecastDirection.bullish,
        entry_price=2049,
        take_profit_price=2075,
        stop_loss_price=2032,
        holding_period="1-3 days",
        intraday_action="等待回踩确认",
        long_term_action="仅适合小仓位研究观察",
        confidence_score=0.62,
        technical_summary="技术面偏强",
        macro_summary="宏观面中性",
        news_summary="新闻面中性",
        risk_summary="波动风险较高",
        agent_votes=[AgentVote(agent="technical", direction=ForecastDirection.bullish, confidence=0.7, rationale="trend")],
        risk_notes=["仅供研究"],
    )


async def test_repository_saves_run_and_latest_forecast() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    run = await repo.create_research_run(input_summary={"symbol": "XAUUSD"})
    saved = await repo.save_forecast(run.id, _forecast())
    await repo.mark_run_success(run.id)
    latest = await repo.get_latest_forecast()
    loaded_run = await repo.get_research_run(run.id)

    assert saved.id is not None
    assert latest is not None
    assert latest.direction == ForecastDirection.bullish
    assert loaded_run is not None
    assert loaded_run.status == "success"
    assert loaded_run.forecast is not None


async def test_repository_records_failed_run() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    run = await repo.create_research_run(input_summary={"symbol": "XAUUSD"})
    await repo.mark_run_failed(run.id, "CSV 缺少 low 字段")
    loaded = await repo.get_research_run(run.id)

    assert loaded is not None
    assert loaded.status == "failed"
    assert loaded.error_message == "CSV 缺少 low 字段"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_persistence.py -q`

Expected: FAIL with missing persistence modules.

- [ ] **Step 3: Implement database and models**

Implement:

- `create_session_factory(database_url: str)` returning an object with `.engine` and async sessionmaker.
- `init_models(engine)` calling `Base.metadata.create_all`.
- `ResearchRunModel` with `id`, `status`, `started_at`, `completed_at`, `input_summary`, `error_message`.
- `ForecastModel` with `id`, `run_id`, timestamp/price/direction/action JSON/text fields and relationship to `ResearchRunModel`.

Use SQLAlchemy JSON columns for `input_summary`, `agent_votes`, `risk_notes`.

- [ ] **Step 4: Implement repository methods**

Implement `ForecastRepository`:

```python
async def create_research_run(self, input_summary: dict[str, object]) -> ResearchRunModel: ...
async def mark_run_success(self, run_id: int) -> None: ...
async def mark_run_failed(self, run_id: int, error_message: str) -> None: ...
async def save_forecast(self, run_id: int, forecast: ForecastResult) -> ForecastResult: ...
async def get_latest_forecast(self) -> ForecastResult | None: ...
async def get_research_run(self, run_id: int) -> ResearchRunResult | None: ...
```

- [ ] **Step 5: Run persistence tests**

Run: `pytest tests/test_persistence.py -q`

Expected: PASS.

If `aiosqlite` is missing, add `aiosqlite>=0.21.0` to the dev dependency group.

---

### Task 4: LangGraph Workflow

**Files:**
- Create: `src/goldfxgraph/workflow/__init__.py`
- Create: `src/goldfxgraph/workflow/graph.py`
- Create: `src/goldfxgraph/workflow/nodes.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: Write failing workflow tests**

Create `tests/test_workflow.py`:

```python
from goldfxgraph.workflow.graph import REQUIRED_NODE_NAMES, build_forecast_graph
from goldfxgraph.workflow.nodes import create_research_forecast_from_inputs
from goldfxgraph.schemas.forecast import CurrentQuote, DailyBar, ForecastDirection
from goldfxgraph.indicators.technical import compute_technical_indicators


def test_graph_contains_required_node_names() -> None:
    graph = build_forecast_graph()

    assert set(REQUIRED_NODE_NAMES).issubset(set(graph.nodes))


def test_forecast_planning_output_is_structured() -> None:
    from datetime import date, datetime, timezone

    bars = [
        DailyBar(date=date(2024, 1, day), open=2000 + day, high=2005 + day, low=1995 + day, close=2002 + day)
        for day in range(1, 31)
    ]
    quote = CurrentQuote(
        current_price=2040,
        data_source="unit",
        data_timestamp=datetime.now(timezone.utc),
    )

    forecast = create_research_forecast_from_inputs(
        latest_bar=bars[-1],
        quote=quote,
        indicators=compute_technical_indicators(bars),
    )

    assert forecast.direction in {ForecastDirection.bullish, ForecastDirection.bearish, ForecastDirection.neutral}
    assert forecast.entry_price > 0
    assert forecast.take_profit_price > 0
    assert forecast.stop_loss_price > 0
    assert forecast.agent_votes
    assert "不构成金融建议" in forecast.disclaimer
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_workflow.py -q`

Expected: FAIL with missing workflow modules.

- [ ] **Step 3: Implement graph builder with explicit nodes**

Create `REQUIRED_NODE_NAMES` exactly:

```python
REQUIRED_NODE_NAMES = [
    "router_validate_request",
    "tool_load_market_data",
    "tool_fetch_current_gold_quote",
    "tool_compute_indicators",
    "agent_technical_analysis",
    "agent_macro_analysis",
    "agent_news_analysis",
    "agent_risk_analysis",
    "agent_forecast_planning",
    "tool_persist_research_run",
    "tool_persist_forecast",
    "router_finalize_result",
]
```

Use `langgraph.graph.StateGraph` and a typed state dict. Add nodes with exactly these names. Keep edges simple and sequential for v1.

- [ ] **Step 4: Implement deterministic fallback planning helper**

Implement `create_research_forecast_from_inputs(...)` as a deterministic helper used by tests and by the planning node when no real agent service is configured. It must not use mock market data; it may derive forecast fields from real quote/bar/indicator inputs. Use Chinese summaries and a research disclaimer.

- [ ] **Step 5: Implement agent node boundaries**

Agent nodes must return structured summary strings and `AgentVote` values. If `GOLDFXGRAPH_AGENT_API_BASE_URL` is configured, call it with `httpx`; if not configured, use the deterministic helper summaries based on real inputs. Do not implement multi-model routing.

- [ ] **Step 6: Run workflow tests**

Run: `pytest tests/test_workflow.py -q`

Expected: PASS.

---

### Task 5: FastAPI API Integration

**Files:**
- Create: `src/goldfxgraph/api/__init__.py`
- Create: `src/goldfxgraph/api/app.py`
- Create: `src/goldfxgraph/api/errors.py`
- Create: `src/goldfxgraph/api/routes.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_api.py`:

```python
from fastapi.testclient import TestClient

from goldfxgraph.api.app import create_app


def test_latest_forecast_returns_empty_when_none_exists() -> None:
    client = TestClient(create_app(testing=True))

    response = client.get("/api/v1/forecast/latest")

    assert response.status_code in {200, 404}
    assert "agent-key" not in response.text


def test_health_endpoint() -> None:
    client = TestClient(create_app(testing=True))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_api.py -q`

Expected: FAIL with missing API modules.

- [ ] **Step 3: Implement app factory and routes**

Implement `create_app(testing: bool = False) -> FastAPI` with `/health` and `/api/v1` router.

Implement:

- `GET /api/v1/forecast/latest`
- `POST /api/v1/research-runs`
- `GET /api/v1/research-runs/{run_id}`

For `testing=True`, use an in-memory repository setup or dependency override that returns empty results without requiring PostgreSQL.

- [ ] **Step 4: Connect research run creation**

`POST /api/v1/research-runs` must create a research run, load CSV, fetch current quote, compute indicators, run workflow, persist forecast, and return `ResearchRunResult`. If quote provider is not configured, return a structured error and record failed run where possible.

- [ ] **Step 5: Run API tests**

Run: `pytest tests/test_api.py -q`

Expected: PASS.

Run: `pytest -q`

Expected: PASS for backend tests implemented so far.

---

### Task 6: Vue 3 Tailwind Dashboard

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/index.html`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/tailwind.config.ts`
- Create: `apps/web/postcss.config.js`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/src/main.ts`
- Create: `apps/web/src/App.vue`
- Create: `apps/web/src/router/index.ts`
- Create: `apps/web/src/styles/main.css`
- Create: `apps/web/src/types/forecast.ts`
- Create: `apps/web/src/services/forecastApi.ts`
- Create: `apps/web/src/constants/forecast.ts`
- Create: `apps/web/src/pages/GoldForecastDashboard.vue`

- [ ] **Step 1: Create frontend project files**

Use Vue 3 Composition API and Tailwind. `package.json` scripts must include:

```json
{
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vue-tsc --noEmit && vite build",
    "typecheck": "vue-tsc --noEmit",
    "lint": "vue-tsc --noEmit"
  }
}
```

- [ ] **Step 2: Implement typed forecast API service**

`apps/web/src/services/forecastApi.ts` must read:

```ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
```

and export:

```ts
export async function fetchLatestForecast(): Promise<ForecastResult | null>
```

Return `null` for `404`; throw an `Error` with a readable message for other failures.

- [ ] **Step 3: Implement dashboard states**

`GoldForecastDashboard.vue` must have `loading`, `error`, `forecast`, `loadForecast()`, and a retry button. It must not contain hard-coded forecast objects. Display empty state when `forecast === null`.

- [ ] **Step 4: Implement dashboard layout**

Display current price, data source/time, direction label, confidence, daily OHLC, entry/take-profit/stop-loss, intraday action, long-term action, holding period, technical/macro/news/risk summaries, agent votes, risk notes, and disclaimer. Keep design dense, professional, and research-oriented; avoid landing-page hero treatment.

- [ ] **Step 5: Run frontend checks**

Run from `apps/web`: `npm install`

Expected: dependencies install successfully. If network is blocked, request escalation.

Run from `apps/web`: `npm run typecheck`

Expected: PASS.

Run from `apps/web`: `npm run build`

Expected: PASS.

---

### Task 7: Validation, OpenSpec Task Updates, And Review

**Files:**
- Modify: `openspec/changes/bootstrap-fullstack-xauusd-forecast-dashboard/tasks.md`
- Read: all changed files

- [ ] **Step 1: Run OpenSpec validation**

Run: `openspec validate bootstrap-fullstack-xauusd-forecast-dashboard --strict`

Expected: `Change 'bootstrap-fullstack-xauusd-forecast-dashboard' is valid`.

- [ ] **Step 2: Run backend validation**

Run:

```bash
pytest
ruff check .
ruff format --check .
pyright
```

Expected: all pass. If `pyright` command is unavailable but dependency exists through project tooling, use the project equivalent and document the exact result.

- [ ] **Step 3: Run frontend validation**

Run:

```bash
cd apps/web
npm run typecheck
npm run build
npm run lint
```

Expected: all pass.

- [ ] **Step 4: Update OpenSpec tasks**

Mark completed implementation items in `openspec/changes/bootstrap-fullstack-xauusd-forecast-dashboard/tasks.md` with `[x]`. Do not archive the change until human review.

- [ ] **Step 5: Final diff review**

Run:

```bash
git status --short
git diff --stat
git diff -- . ':!data/raw/xauusd_d.csv'
```

Expected: only intended files changed; no real secrets; no automatic trading, broker, n8n, MCP, multi-model routing, scorecard, full evaluation system, or complex observability.

---

## Self-Review

- Spec coverage: backend API, settings, CSV, current quote, indicators, LangGraph nodes, structured forecast, PostgreSQL, Vue Dashboard, and validation are all covered by Tasks 1-7.
- Placeholder scan: no `TBD`, `TODO`, or unresolved “implement later” instructions remain.
- Type consistency: model names use `ForecastResult`, `ResearchRunResult`, `DailyBar`, `CurrentQuote`, `TechnicalIndicators`, `AgentVote`; ORM names use `ResearchRunModel` and `ForecastModel`; API paths match `/api/v1/forecast/latest`, `/api/v1/research-runs`, `/api/v1/research-runs/{run_id}`.
