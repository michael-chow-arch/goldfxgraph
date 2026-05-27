# GoldFXGraph 市场数据数据库化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 XAUUSD 日线 CSV 降级为一次性初始化导入源，后续的预测、评估和定时任务全部改为从 PostgreSQL 读取和写入市场数据，不再在运行期直接读取 CSV。

**Architecture:** 新增独立的市场数据持久化边界，把 `DailyBar` 从文件输入转成数据库实体，统一由 repository 提供读取接口。CSV 只保留为初始化导入材料，导入动作通过单独 CLI 执行且必须幂等；运行时的 workflow、收盘后评估和历史查询都只访问数据库，缺少初始化数据时明确失败或 no-op。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, PostgreSQL, Pydantic v2, pandas, pytest, ruff, Typer/argparse CLI patterns, Vue 3 + TypeScript（仅在类型或展示需要时）。 

---

## File Structure

- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/persistence/models.py`: 新增市场数据表模型，例如 `MarketDataBarModel`。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/persistence/repositories.py`: 新增市场数据写入与查询接口，供 workflow 和 scheduler 使用。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/persistence/database.py` 或新增迁移脚本位置：确保新表能在 `init_models` 或迁移流程中创建。
- Create `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/market_data/ingest.py`: CSV 初始化导入逻辑，负责把 `DailyBar` 批量写入数据库。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/backfill/eod_backfill.py`: 改为从数据库读取最新日线和缺失区间，不再读取 CSV。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/backfill/eod_evaluation.py`: 改为从数据库读取结算 bar 和历史预测，不再读取 CSV。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/workflow/nodes.py`: `tool_load_market_data` 改为 DB 驱动。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/workflow/graph.py`: 保持节点顺序不变，但让数据源切换到数据库边界。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/backfill/cli.py`: 增加初始化导入命令入口，例如 `ingest` 或 `import-market-data`。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/cli.py`: 统一分发 `ingest` / `backfill` / `evaluate` 命令。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/packages/common/settings.py`: 如需配置初始化导入路径、市场数据表相关开关，在此集中定义。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_market_data.py`: 新增 CSV 初始导入行为测试。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_backfill.py`: 调整为不再依赖 CSV 运行时读取。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_forecast_evaluation_scheduler.py`: 调整为从数据库读取结算日线。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_workflow.py`: 调整 `tool_load_market_data` 的来源契约。
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_api.py` 或新增仓储测试文件：补齐空库、幂等导入和历史读取测试。

## 1. 市场数据持久化

**目标：** 把 XAUUSD 日线从“文件读取结构”变成“数据库事实表”，让后续所有分析逻辑只依赖数据库。

**Files:**
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/persistence/models.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/persistence/repositories.py`
- Create `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_market_data_repository.py`

- [ ] **Step 1: 先写市场数据仓储的失败测试**

  在 `tests/test_market_data_repository.py` 里先写最小失败用例，覆盖以下行为：

  - `MarketDataBarModel` 可以被导入
  - `MarketDataRepository.upsert_market_bars(...)` 可以批量写入日线
  - `MarketDataRepository.get_latest_market_bar(symbol)` 可以返回最新 completed bar
  - `MarketDataRepository.get_market_bars_between(symbol, start_date, end_date)` 可以返回按日期排序的区间数据

  运行：

  ```bash
  pytest tests/test_market_data_repository.py -q
  ```

  预期：当前失败，因为市场数据表和仓储接口还未实现。

- [ ] **Step 2: 实现市场数据表与仓储**

  在 `src/goldfxgraph/persistence/models.py` 中新增 `MarketDataBarModel`，建议字段至少包括：

  - `id`
  - `symbol`
  - `bar_date`
  - `open`
  - `high`
  - `low`
  - `close`
  - `volume`
  - `source`
  - `created_at`
  - `updated_at`

  约束建议：

  - `symbol + bar_date` 唯一
  - `bar_date` 使用 date，不要用自由文本
  - 价格字段保持正数校验

  在 `src/goldfxgraph/persistence/repositories.py` 中新增：

  - `upsert_market_bars(bars: list[DailyBar]) -> int`
  - `get_latest_market_bar(symbol: str = "XAUUSD") -> DailyBar | None`
  - `get_market_bars_between(symbol: str, start_date: date, end_date: date) -> list[DailyBar]`
  - `get_market_bars_for_date(symbol: str, target_date: date) -> DailyBar | None`
  - `get_market_bars_count(symbol: str = "XAUUSD") -> int`

  仓储返回值保持和现有 `DailyBar` / `MarketDataSet` 一致，避免上层 workflow 再做额外转换。

- [ ] **Step 3: 让仓储测试通过并核对幂等行为**

  重新运行：

  ```bash
  pytest tests/test_market_data_repository.py -q
  ```

  预期：通过。

  再确认重复写入同一天数据时不会生成重复记录，幂等行为保持稳定。

## 2. 初始化导入命令

**目标：** 提供一个单独的“只初始化导入”入口，把 CSV 内容一次性写入数据库，之后运行时不再依赖 CSV。

**Files:**
- Create `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/market_data/ingest.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/backfill/cli.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/cli.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_market_data.py`

- [ ] **Step 1: 先写初始化导入失败测试**

  在 `tests/test_market_data.py` 增加测试，覆盖以下行为：

  - 读取 `data/raw/xauusd_daily.csv` 后能写入数据库
  - 第二次导入不会重复创建同一日期的 bar
  - CSV 缺少必填列时会抛出可读错误

  运行：

  ```bash
  pytest tests/test_market_data.py -q
  ```

  预期：当前失败，因为导入模块和仓储还未接通。

- [ ] **Step 2: 实现 CSV 初始化导入流程**

  在 `src/goldfxgraph/market_data/ingest.py` 中新增：

  - `import_xauusd_daily_csv_to_db(csv_path: Path, repository: MarketDataRepository) -> int`
  - `validate_market_data_ready(...)`
  - `build_market_data_set_from_csv(...)`（如果需要保留结构化转换）

  导入逻辑要求：

  - 只做初始化，不做定时重复补数
  - 幂等
  - 默认按日期升序导入
  - 导入结束后可返回写入条数和最新日期

  CLI 入口建议新增：

  - `goldfxgraph ingest-market-data`
  - 或 `goldfxgraph import-market-data`

  命令参数建议：

  - `--csv-path`
  - `--env-file`
  - `--symbol`

  `src/goldfxgraph/cli.py` 负责把新命令分发到导入逻辑。

- [ ] **Step 3: 让导入测试通过并验证幂等**

  再次运行：

  ```bash
  pytest tests/test_market_data.py -q
  ```

  预期：通过。

  再手工运行一次导入命令，确认第二次执行不会重复插入相同 bar。

## 3. 运行时只读数据库

**目标：** 把 workflow、收盘评估和定时任务的运行时市场数据来源统一切到数据库，彻底移除 CSV 运行期读取路径。

**Files:**
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/workflow/nodes.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/backfill/eod_backfill.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/src/goldfxgraph/backfill/eod_evaluation.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_backfill.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_forecast_evaluation_scheduler.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_workflow.py`

- [ ] **Step 1: 先写运行时只读数据库的失败测试**

  在 `tests/test_workflow.py` 和 `tests/test_forecast_evaluation_scheduler.py` 里补测试，覆盖以下行为：

  - workflow 从 repository 读取最新 market data，不再依赖 CSV 路径
  - 收盘评估从数据库读取结算 bar
  - 当数据库没有对应 symbol/bar 时返回明确的 skipped / no-op

  运行：

  ```bash
  pytest tests/test_workflow.py tests/test_forecast_evaluation_scheduler.py -q
  ```

  预期：当前失败，因为 `tool_load_market_data` 和 scheduler 仍可能依赖 CSV。

- [ ] **Step 2: 改造 workflow 和 scheduler 数据源**

  在 `src/goldfxgraph/workflow/nodes.py` 中：

  - `tool_load_market_data` 改成调用 `MarketDataRepository.get_latest_market_bar(...)` 和 `get_market_bars_between(...)`
  - 不再通过 `load_xauusd_daily_csv` 读取运行期数据
  - 没有初始化数据时，抛出明确错误，提示先执行导入命令

  在 `src/goldfxgraph/backfill/eod_evaluation.py` 中：

  - 用数据库查询目标交易日的结算 bar
  - 用数据库查询当日 forecast 历史
  - 不再读取 CSV 文件

  在 `src/goldfxgraph/backfill/eod_backfill.py` 中：

  - 如果这条定时任务还需要追加市场数据，应改成向数据库写入，不再回写 CSV
  - 如果未来不再追加市场数据，则将该模块收敛为纯评估/维护任务，避免文件写入逻辑混杂

  需要的话，顺便把 `settings.xauusd_csv_path` 的运行时依赖降级成“仅导入时使用”。

- [ ] **Step 3: 让运行时测试通过并检查错误语义**

  再次运行：

  ```bash
  pytest tests/test_workflow.py tests/test_forecast_evaluation_scheduler.py tests/test_backfill.py -q
  ```

  预期：通过。

  并确认：

  - 未初始化市场数据时，错误信息能提示先导入
  - 历史评估和 forecast 读取都只走数据库

## 4. 收尾验证与文档同步

**目标：** 确保数据库化之后，代码、测试、CLI、OpenSpec/计划文档保持一致。

**Files:**
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_api.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_market_data_repository.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_market_data.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_backfill.py`
- Modify `/Users/admin/.codex/worktrees/e438/goldfxgraph/tests/test_forecast_evaluation_scheduler.py`

- [ ] **Step 1: 补齐 API / CLI 兼容测试**

  确认下面这些接口在市场数据数据库化后仍然通过：

  - `POST /api/v1/research-runs`
  - `GET /api/v1/forecast/latest`
  - `GET /api/v1/forecast/history`
  - `goldfxgraph ingest-market-data`
  - `goldfxgraph backfill`
  - `goldfxgraph evaluate`

- [ ] **Step 2: 跑完整验证**

  运行：

  ```bash
  pytest -q
  ruff check src tests
  ```

  预期：测试和 lint 通过。

- [ ] **Step 3: 复查迁移边界**

  最后确认：

  - CSV 只在初始化导入时出现
  - workflow / scheduler / evaluation 运行期不再读 CSV
  - 数据缺失时有明确错误或 no-op

