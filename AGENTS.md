# AGENTS.md

## 1. Project Identity

This repository is `GoldFXGraph`.

GoldFXGraph is a full-stack gold research project for XAUUSD daily and near-real-time analysis.

The system should:

- read real XAUUSD market data
- fetch current/latest gold data when required
- compute deterministic technical indicators
- run explicit LangGraph multi-agent analysis
- produce structured forecast results
- persist research runs and forecasts
- display the forecast result in a Vue 3 + Tailwind frontend

This project is for research and decision support only.

Do not implement automatic trading, broker integration, real order execution, MCP, n8n, multi-model routing, full evaluation jobs, scorecards, or complex observability unless explicitly requested.

---

## 2. Repository Layout

Use a professional full-stack layout.

Expected structure:

```text
goldfxgraph/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── openspec/
├── data/
│   └── raw/
├── src/
│   └── goldfxgraph/
├── tests/
└── apps/
    └── web/
        ├── package.json
        ├── index.html
        ├── vite.config.ts
        ├── tailwind.config.ts
        ├── postcss.config.js
        └── src/
            ├── main.ts
            ├── App.vue
            ├── router/
            │   └── index.ts
            ├── styles/
            │   └── main.css
            ├── pages/
            │   └── GoldForecastDashboard.vue
            ├── components/
            ├── services/
            ├── types/
            └── constants/
```

Backend application code must live under:

```text
src/goldfxgraph/
```

Backend tests must live under:

```text
tests/
```

Frontend application code must live under:

```text
apps/web/src/
```

Frontend global CSS must live under:

```text
apps/web/src/styles/main.css
```

OpenSpec files must live under:

```text
openspec/
```

Do not invent a different package structure unless the user explicitly approves it.

---

## 3. OpenSpec Rules

This project uses OpenSpec for non-trivial changes.

OpenSpec paths:

```text
openspec/specs/
openspec/changes/
openspec/changes/archive/
```

For any feature, architecture change, workflow change, database change, API change, or frontend module:

1. Read `AGENTS.md`.
2. Inspect existing code and OpenSpec files.
3. Create or update an OpenSpec change first.
4. Generate or update:
   - `proposal.md`
   - `design.md`
   - `tasks.md`
   - spec delta files
5. Stop for human review before implementation.
6. Apply the change only after approval.
7. Validate and archive after implementation.

Preferred OpenSpec commands:

```text
/spec propose <change-id>
/spec apply <change-id>
/spec archive <change-id>
```

If this project uses `/opsx:*` instead, use the equivalent OpenSpec commands.

Recommended first change:

```text
bootstrap-fullstack-xauusd-forecast-dashboard
```

This change should cover the initial backend workflow and the first Vue 3 forecast dashboard.

---

## 4. Superpowers Rules

This project uses Superpowers as the execution discipline.

OpenSpec defines what to build.  
Superpowers defines how to execute safely.

Use Superpowers skills explicitly when useful:

```text
brainstorming
writing-plans
test-driven-development
executing-plans
requesting-code-review
finishing-a-development-branch
```

During implementation:

1. Create an implementation plan from the OpenSpec change.
2. Implement one small task at a time.
3. Write or update tests where practical.
4. Run tests directly.
5. Fix failures directly.
6. Update `tasks.md`.
7. Review the diff before completion.

Do not ask the user to run tests manually unless credentials, permissions, or local services prevent the agent from running them.

---

## 5. Frontend Rules

The frontend uses:

```text
Vue 3
TypeScript
Vite
Tailwind CSS
```

Frontend root:

```text
apps/web/
```

Frontend global stylesheet:

```text
apps/web/src/styles/main.css
```

Use `ui-ux-pro-max` for frontend UI/UX design guidance or review before implementing dashboards, reports, layout, interaction, or visual design.

Frontend tasks should:

1. Clarify user flow and page purpose.
2. Produce a clean UI/UX plan before coding.
3. Keep visual design consistent.
4. Avoid generic placeholder UI.
5. Review final UI against the intended user experience.

Do not change frontend architecture or design system without approval.

---

## 6. Gold Forecast Dashboard Requirements

The main frontend page should show the gold forecast result.

Recommended page:

```text
apps/web/src/pages/GoldForecastDashboard.vue
```

The dashboard should display at least:

- current/latest XAUUSD price
- data timestamp
- data source
- daily open, high, low, close when available
- multi-agent analysis summary
- technical analysis summary
- macro or news analysis summary when available
- final forecast direction
- entry price
- take-profit price
- stop-loss price
- risk/reward ratio when available
- suggested holding period
- intraday action suggestion
- longer-term holding suggestion
- confidence score
- key risks
- disclaimer that this is research, not financial advice

Forecast direction should use structured values such as:

```text
bullish
bearish
neutral
```

Chinese UI labels can use:

```text
看多
看空
震荡/中性
```

Trading decision fields should be clearly separated from research explanation:

```text
entry_price
take_profit_price
stop_loss_price
holding_period
intraday_action
long_term_action
confidence_score
risk_notes
```

Do not hide important forecast data inside free-form text only.

---

## 7. Market Data Rules

Use real market data.

The first backend version can use user-provided XAUUSD daily CSV data.

Default CSV path:

```text
data/raw/xauusd_daily.csv
```

CSV path must be configurable through:

```text
GOLDFXGRAPH_XAUUSD_CSV_PATH
```

Required CSV columns:

```text
date
open
high
low
close
```

Optional CSV columns:

```text
volume
source
symbol
```

The CSV loader must validate required columns, sort by date, and select the latest available completed daily bar.

When the workflow needs current/latest gold data, the agent or backend should fetch it through an approved data source or tool, record the source and timestamp, and keep it separate from completed daily CSV bars.

Do not use mock market data in the main workflow.

---

## 8. Backend API Requirements

Expose API endpoints only after the OpenSpec change defines them.

Recommended initial API:

```text
GET /api/v1/forecast/latest
POST /api/v1/research-runs
GET /api/v1/research-runs/{run_id}
```

The frontend should call the backend through a typed service layer.

Recommended frontend service path:

```text
apps/web/src/services/forecastApi.ts
```

Recommended frontend types path:

```text
apps/web/src/types/forecast.ts
```

Frontend API base URL should come from:

```text
VITE_API_BASE_URL
```

Do not hard-code backend URLs in Vue components.

---

## 9. Multi-Agent Analysis Rules

Use explicit LangGraph node names.

Preferred node names:

```text
router_validate_request
tool_load_market_data
tool_fetch_current_gold_quote
tool_compute_indicators
agent_technical_analysis
agent_macro_analysis
agent_news_analysis
agent_risk_analysis
agent_forecast_planning
tool_persist_research_run
tool_persist_forecast
router_finalize_result
```

Avoid vague names:

```text
process
analyze
handle
run_agent
execute
```

Separate responsibilities:

- tool nodes: deterministic work such as loading data, fetching quotes, computing indicators, and persistence
- agent nodes: structured reasoning and forecast decisions
- router nodes: validation and routing

---

## 10. Structured Forecast Output

Use Pydantic models for backend forecast output.

The forecast output should include at least:

```text
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
```

Do not return only free-form text.

---

## 11. Configuration and Secrets

Never commit real secrets.

Do not put real credentials in:

```text
AGENTS.md
README.md
OpenSpec files
source code
tests
frontend files
```

Use local `.env` files or cloud secrets for real values.

Allowed committed file:

```text
.env.example
```

Required backend environment variables:

```env
GOLDFXGRAPH_ENV=local
GOLDFXGRAPH_LOG_LEVEL=INFO
GOLDFXGRAPH_DATABASE_URL=postgresql+asyncpg://goldfxgraph:change_me@localhost:5432/goldfxgraph
GOLDFXGRAPH_XAUUSD_CSV_PATH=data/raw/xauusd_daily.csv
```

Required frontend environment variables:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Preferred backend settings module:

```text
src/goldfxgraph/packages/common/settings.py
```

---

## 12. Docker Compose

The repository root contains:

```text
docker-compose.yml
```

Use it for local infrastructure such as PostgreSQL.

Before changing infrastructure, inspect the existing `docker-compose.yml`.

Preferred local startup command:

```bash
docker compose up -d
```

Do not replace `docker-compose.yml` unless necessary.

---

## 13. Persistence Rules

Use PostgreSQL for persistence.

Database URL must come from:

```text
GOLDFXGRAPH_DATABASE_URL
```

Keep SQLAlchemy ORM class names with the `Model` suffix, for example:

```text
ResearchRunModel
ForecastModel
EvaluationRecordModel
MemoryItemModel
```

Do not rename ORM models to `Table`.

Avoid string-based dynamic imports for SQLAlchemy metadata registration.

Use explicit, typed, maintainable persistence boundaries.

---

## 14. Python Engineering Rules

Use professional Python engineering practices.

Prefer:

- typed functions
- Pydantic models
- async I/O where appropriate
- clear module boundaries
- deterministic tools
- small functions
- explicit exceptions
- tests for important behavior

Code comments, important inline explanations, and complex design notes should be written in Chinese. Keep standard technical terms in English when clearer.

Do not write large untyped scripts.

Do not hide business logic only inside prompts.

---

## 15. Frontend Engineering Rules

Use professional Vue 3 engineering practices.

Prefer:

- Vue 3 Composition API
- TypeScript
- typed API responses
- reusable components
- Tailwind utility classes
- centralized constants
- clean loading, empty, error, and success states

Use `apps/web/src/styles/main.css` for global Tailwind imports and shared base styles.

Do not put large API logic directly inside Vue pages.

Do not hard-code forecast mock data in the production dashboard.

---

## 16. Testing and Validation

Run relevant checks directly.

Preferred backend commands, if available:

```bash
pytest
ruff check .
ruff format --check .
mypy .
openspec validate --all
```

Preferred frontend commands, if available:

```bash
cd apps/web
npm install
npm run lint
npm run typecheck
npm run build
```

If the project uses different commands, inspect `pyproject.toml` and `apps/web/package.json` first.

When tests fail:

1. Inspect the failure.
2. Fix the issue.
3. Rerun relevant tests.
4. Summarize the cause and fix.

Do not claim completion without validation results.

---

## 17. Git Rules

Use a feature branch or Codex worktree for non-trivial work.

Recommended branch for the first full-stack workflow:

```text
feature/bootstrap-fullstack-xauusd-forecast-dashboard
```

Preferred commit style:

```text
spec: propose fullstack xauusd forecast dashboard
feat: implement fullstack xauusd forecast dashboard
chore: archive fullstack xauusd forecast dashboard spec
```

Do not commit secrets.

Do not modify unrelated files.

Show the final diff before commit when possible.

---

## 18. Standard Workflow

For major changes:

1. Read `AGENTS.md`.
2. Inspect repository structure.
3. Inspect `pyproject.toml`.
4. Inspect `docker-compose.yml`.
5. Inspect frontend files if `apps/web/` exists.
6. Inspect existing OpenSpec files.
7. Create or update an OpenSpec change.
8. Stop for human review.
9. Use Superpowers to create an implementation plan.
10. Apply the OpenSpec change.
11. Implement with tests.
12. Run backend and frontend validation.
13. Review the diff.
14. Archive the OpenSpec change.
15. Show final results.

---

## 19. Chinese Output Rules

All OpenSpec and Superpowers outputs should be written in Chinese by default.

This includes:

- OpenSpec proposal descriptions
- OpenSpec design explanations
- OpenSpec tasks
- OpenSpec spec scenarios and acceptance criteria
- Superpowers brainstorming output
- Superpowers implementation plans
- Superpowers TDD notes
- Superpowers code review comments
- Superpowers final summaries
- user-facing explanations
- code comments and complex inline explanations

Keep the following items in English when appropriate:

- file names
- directory names
- package names
- class names
- function names
- variable names
- API paths
- command names
- tool names
- framework names
- technical keywords that are clearer in English

For OpenSpec files, write the main content in Chinese, but keep required OpenSpec structural keywords or headings unchanged if the tool requires them.

For example:

- `proposal.md` content should be Chinese.
- `design.md` content should be Chinese.
- `tasks.md` task descriptions should be Chinese.
- spec scenario descriptions should be Chinese.
- commands such as `/spec propose`, `/spec apply`, `pytest`, `ruff check .` should remain unchanged.

If the user writes in Chinese, continue in Chinese unless explicitly requested otherwise.

---

## 20. Do Not Do

Do not:

- bypass OpenSpec for major changes
- implement large features without a reviewed change
- hard-code database credentials
- hard-code frontend API URLs
- commit `.env`
- use mock market data in the main workflow
- invent a new package structure
- implement trading
- implement n8n
- implement MCP
- implement scorecards or evaluation jobs before requested
- replace `docker-compose.yml` unnecessarily
- declare completion without tests or validation
