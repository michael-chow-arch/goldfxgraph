# Gold Dashboard Redesign And EOD Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 GoldFXGraph 的黄金研究 Dashboard 升级为更专业的深色金融研究面板，并新增一个美国收市后的每日 CSV 补数任务，自动检查缺失日线并在校验后补齐。

**Architecture:** 前端和后端分成两条独立实现线。前端只改 `apps/web/` 下的视觉和信息组织，不改变 API contract；后端新增独立的 backfill 服务与 CLI 入口，复用现有 CSV loader、CurrentQuoteProvider、agent client 和持久化边界，补数过程采用 agent-assisted discovery + deterministic validation + atomic CSV write。两条线共享同一套 forecast schema、配置和研究-only 约束。

**Tech Stack:** Python 3.12, pandas, httpx, Pydantic v2, FastAPI, LangGraph, pytest, ruff, pyright, Vue 3, TypeScript, Vite, Tailwind CSS.

---

## File Structure

- Modify `apps/web/src/pages/GoldForecastDashboard.vue`: 重新组织首屏、OHLC、交易字段、agent 摘要、风险和免责声明的视觉层级。
- Modify `apps/web/src/styles/main.css`: 增加深色金色研究面板的全局背景、字体和 panel 样式。
- Modify `apps/web/src/constants/forecast.ts`: 调整方向色板、摘要分区或文案常量，保持页面一致性。
- Modify `apps/web/src/components/` and `apps/web/src/pages/` only if需要抽出新组件，避免页面文件继续膨胀。
- Modify `src/goldfxgraph/market_data/csv_loader.py`: 增加缺失日期识别所需的辅助函数或导出。
- Create `src/goldfxgraph/backfill/__init__.py`: 新增 backfill 包入口。
- Create `src/goldfxgraph/backfill/eod_backfill.py`: 计算最新日期、识别缺口、调用 agent-assisted query、验证并写回 CSV。
- Create `src/goldfxgraph/backfill/cli.py`: 提供独立命令入口，便于调度层在美国收市后触发。
- Create `src/goldfxgraph/cli.py`: 对接 `project.scripts` 入口，转发到 backfill CLI 或保留未来扩展点。
- Modify `src/goldfxgraph/llm/openai_client.py` only if backfill 的 agent 查询需要更明确的结构化请求边界。
- Modify `src/goldfxgraph/packages/common/settings.py`: 如需补充 backfill 调度窗口或数据源配置，则在此添加可配置项。
- Create `tests/test_backfill.py`: 覆盖日期缺口、候选数据校验、原子写回和 CLI 行为。
- Modify `tests/test_market_data.py`: 如需补充 CSV 日期排序或缺口辅助测试。
- Modify `tests/test_workflow.py` / `tests/test_api.py` only if frontend/backfill work unexpectedly影响现有研究 contract。
- Modify `openspec/changes/gold-dashboard-redesign-and-eod-backfill/tasks.md`: 在每个任务完成后勾选。

## Task 1: Dashboard Visual Redesign

**Files:**
- Modify `apps/web/src/pages/GoldForecastDashboard.vue`
- Modify `apps/web/src/styles/main.css`
- Modify `apps/web/src/constants/forecast.ts`
- Test `apps/web` via `npm run typecheck` / `npm run build`

- [ ] **Step 1: Re-read the current dashboard structure and map the new layout blocks**

Focus on the existing data contract in `apps/web/src/types/forecast.ts` and keep all API data fields visible. The new layout must prioritize:
- latest XAUUSD price, direction, confidence
- data timestamp and data source
- OHLC block
- entry / take-profit / stop-loss / holding period / intraday action / long-term action
- technical / macro / news / risk summaries
- agent votes
- risk notes and disclaimer

- [ ] **Step 2: Write the visual tokens first**

Update `apps/web/src/styles/main.css` so the page uses a premium dark research cockpit style:
- dark slate background with subtle gold accent
- stronger panel borders and glow
- monospace emphasis for numbers
- readable body font
- accessible focus states and reduced-motion support

If any shared labels or direction colors need refinement, update `apps/web/src/constants/forecast.ts` rather than hard-coding styles inside the Vue template.

- [ ] **Step 3: Restructure the page into smaller visual sections**

Refactor `GoldForecastDashboard.vue` into clear sections with stable responsive behavior:
- hero / headline summary
- status strip
- core forecast panel
- OHLC and execution metrics
- summaries and risk notes
- agent votes and disclaimer

Keep loading/error/empty states visually consistent with the new theme. Avoid changing the API call contract or inventing mock forecast data.

- [ ] **Step 4: Verify responsive behavior on mobile and desktop**

Make sure the page collapses into vertical stacks on narrow screens and preserves readable spacing at tablet and desktop widths. Keep all interactive elements keyboard accessible and avoid layout shifts on hover.

- [ ] **Step 5: Run frontend validation**

Run:

```bash
cd apps/web
npm run typecheck
npm run build
```

Expected: both commands pass without type errors or build failures.

## Task 2: End-Of-Day Backfill Pipeline

**Files:**
- Create `src/goldfxgraph/backfill/__init__.py`
- Create `src/goldfxgraph/backfill/eod_backfill.py`
- Create `src/goldfxgraph/backfill/cli.py`
- Create `src/goldfxgraph/cli.py`
- Modify `src/goldfxgraph/market_data/csv_loader.py`
- Modify `src/goldfxgraph/packages/common/settings.py` if backfill config is needed
- Create `tests/test_backfill.py`
- Modify `tests/test_market_data.py` if helper coverage is needed

- [ ] **Step 1: Write failing backfill tests**

Create `tests/test_backfill.py` with concrete coverage for:
- extracting the latest completed CSV date
- computing missing trading days
- rejecting invalid candidate bars
- preserving the original CSV when a write fails
- exposing a CLI entry that can be called from a scheduler

Use temporary files and deterministic fixtures only. Do not depend on a live market API for these tests.

- [ ] **Step 2: Inspect existing CSV and quote helpers**

Reuse the current `load_xauusd_daily_csv()` output and `CurrentQuoteProvider` patterns instead of building a second market data stack. The backfill module should consume the existing schema and keep source provenance intact.

- [ ] **Step 3: Implement missing-date detection**

Add a deterministic helper that compares the latest CSV date with the expected daily trading sequence and returns the missing dates in ascending order. Keep the logic timezone-aware and explicit about the U.S. close window assumption.

- [ ] **Step 4: Implement agent-assisted candidate discovery and validation**

Use the existing agent client boundary to query for candidate OHLC bars for each missing date, then validate:
- required fields present
- date matches the missing trading day
- symbol is consistent
- OHLC range is sane
- duplicate rows are not introduced

Only valid rows may proceed to persistence.

- [ ] **Step 5: Implement atomic CSV write-back**

Write to a temporary file first, then atomically replace the original CSV. Preserve existing rows, append new rows in chronological order, and ensure failure paths leave the original file untouched.

- [ ] **Step 6: Add an executable CLI**

Expose a simple command that a scheduler can call after the U.S. gold market close. The CLI should:
- load settings
- run the backfill workflow
- print a concise success/no-op/failure result
- exit non-zero on failure

- [ ] **Step 7: Run backend validation**

Run:

```bash
pytest tests/test_backfill.py tests/test_market_data.py -q
ruff check src tests
```

Expected: tests and lint pass after the implementation lands.

## Task 3: Integration Review

**Files:**
- Review `apps/web/src/pages/GoldForecastDashboard.vue`
- Review `src/goldfxgraph/backfill/eod_backfill.py`
- Review `src/goldfxgraph/backfill/cli.py`
- Review `tests/test_backfill.py`

- [ ] **Step 1: Verify no scope creep**

Confirm the implementation still stays research-only:
- no automatic trading
- no broker integration
- no mock market data in the main workflow
- no hidden API contract changes for the dashboard

- [ ] **Step 2: Verify spec coverage**

Check the OpenSpec change artifacts against the implementation:
- `gold-forecast-dashboard`
- `daily-market-data-backfill`

Make sure each requirement has a corresponding code path and test.

- [ ] **Step 3: Final diff review and task close-out**

Review the final diff for readability, file ownership boundaries, and obvious regressions. Then update `openspec/changes/gold-dashboard-redesign-and-eod-backfill/tasks.md` to reflect completed items.
