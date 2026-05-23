# OpenAI-Compatible Agents And Auto Quote Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 GoldFXGraph 后端直接兼容 OpenAI 风格配置，并在无手工 quote URL 的情况下自动获取实时黄金价格后完成结构化研究流程。

**Architecture:** 保持现有 FastAPI + LangGraph + PostgreSQL 边界不变，只替换三层能力：settings 增加 OpenAI/DATABASE 别名兼容；workflow agent 节点改为通过一个小型 OpenAI-compatible client 获取结构化分析；current quote 改为工具节点内部自动尝试候选公开 source，并统一转换成 `CurrentQuote`。所有失败路径继续走受控错误或 deterministic fallback，不改前端 contract。

**Tech Stack:** Python 3.12, FastAPI, httpx, Pydantic v2, LangGraph, SQLAlchemy async, pytest, ruff, pyright.

---

## File Structure

- Modify: `src/goldfxgraph/packages/common/settings.py`  
  扩展 settings 字段与 env alias 兼容逻辑，支持 `DATABASE_URL`、`OPENAI_API_KEY`、`GOLDFXGRAPH_OPENAI_MODEL`、`GOLDFXGRAPH_OPENAI_BASE_URL`。
- Modify: `.env.example`  
  更新示例变量名为 OpenAI 风格兼容版本，仅保留 placeholder。
- Modify: `dev.env`  
  更新本地开发变量约定，但 committed 内容仍保持 placeholder。
- Create: `src/goldfxgraph/llm/__init__.py`  
  暴露 OpenAI-compatible client 边界。
- Create: `src/goldfxgraph/llm/openai_client.py`  
  统一封装 model/base_url/api_key、发送请求、解析结构化 JSON、抛出稳定错误。
- Modify: `src/goldfxgraph/market_data/current_quote.py`  
  从单 URL provider 改为候选 source 自动尝试逻辑，并保留 fallback/source 脱敏能力。
- Modify: `src/goldfxgraph/workflow/nodes.py`  
  用 OpenAI-compatible client 驱动技术/宏观/新闻/风险 agent；quote tool 改为自动 discovery。
- Modify: `src/goldfxgraph/api/routes.py`  
  让研究接口适配新的 quote failure / model failure 语义。
- Modify: `tests/test_settings.py`  
  覆盖 env alias、优先级、secret 不泄露。
- Modify: `tests/test_market_data.py`  
  覆盖 quote discovery 成功、顺序回退、全部失败、source 脱敏。
- Create: `tests/test_openai_client.py`  
  覆盖 OpenAI-compatible client 的成功、非 JSON、坏结构和 header 行为。
- Modify: `tests/test_workflow.py`  
  覆盖 workflow 在配置可用时调用 OpenAI-compatible client，在失败时 fallback。
- Modify: `tests/test_api.py`  
  覆盖无手工 quote URL 也能研究、quote discovery 失败时返回结构化错误。
- Modify: `openspec/changes/openai-compatible-agents-and-auto-quote-discovery/tasks.md`  
  每完成一项立即勾选。

### Task 1: Settings And OpenAI-Compatible Client

**Files:**
- Modify: `src/goldfxgraph/packages/common/settings.py`
- Modify: `.env.example`
- Modify: `dev.env`
- Create: `src/goldfxgraph/llm/__init__.py`
- Create: `src/goldfxgraph/llm/openai_client.py`
- Modify: `tests/test_settings.py`
- Create: `tests/test_openai_client.py`

- [ ] **Step 1: 扩展 settings 测试，先写失败用例**

在 `tests/test_settings.py` 增加以下测试：

```python
def test_settings_accepts_database_url_and_openai_aliases(tmp_path: Path) -> None:
    env_file = tmp_path / "dev.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql+asyncpg://goldfxgraph:goldfxgraph@localhost:5432/goldfxgraph",
                "OPENAI_API_KEY=test-openai-key",
                "GOLDFXGRAPH_OPENAI_MODEL=gpt-5.1",
                "GOLDFXGRAPH_OPENAI_BASE_URL=https://api.zhizengzeng.com/v1",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)

    assert settings.database_url == "postgresql+asyncpg://goldfxgraph:goldfxgraph@localhost:5432/goldfxgraph"
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "test-openai-key"
    assert settings.openai_model == "gpt-5.1"
    assert settings.openai_base_url == "https://api.zhizengzeng.com/v1"
```

再新增优先级测试，验证 `GOLDFXGRAPH_DATABASE_URL` 高于 `DATABASE_URL`。

- [ ] **Step 2: 为 OpenAI-compatible client 写失败测试**

创建 `tests/test_openai_client.py`，至少包含：

```python
def test_openai_client_sends_bearer_header_and_parses_structured_result() -> None: ...
def test_openai_client_rejects_non_json_response() -> None: ...
def test_openai_client_rejects_invalid_structured_payload() -> None: ...
```

成功用例断言请求 URL 为 `https://api.zhizengzeng.com/v1/chat/completions`，并且不会把 key 写进 payload。

- [ ] **Step 3: 跑 settings/client 测试，确认先失败**

Run:

```bash
uv run pytest tests/test_settings.py tests/test_openai_client.py -q
```

Expected: FAIL，提示缺少 `openai_*` 字段或 client 模块不存在。

- [ ] **Step 4: 实现 settings 兼容层**

在 `src/goldfxgraph/packages/common/settings.py`：

- 为 `GoldFXGraphSettings` 增加：
  - `openai_api_key: SecretStr | None`
  - `openai_model: str | None`
  - `openai_base_url: str | None`
- 读取顺序：
  1. `GOLDFXGRAPH_DATABASE_URL` / `GOLDFXGRAPH_OPENAI_*`
  2. `DATABASE_URL` / `OPENAI_API_KEY`
  3. 默认值
- 保持 `repr` 不泄露 secret。

- [ ] **Step 5: 实现 OpenAI-compatible client**

在 `src/goldfxgraph/llm/openai_client.py` 定义：

```python
class OpenAIClientError(RuntimeError): ...

class OpenAIAgentClient:
    def __init__(self, *, base_url: str, model: str, api_key: str, transport: httpx.BaseTransport | None = None) -> None: ...
    def invoke_agent(self, *, agent_name: str, payload: dict[str, object]) -> AgentApiResponse: ...
```

实现要点：
- POST 到 `{base_url.rstrip('/')}/chat/completions`
- 用 `Authorization: Bearer ...`
- 使用单条 system prompt + user payload
- 要求返回 JSON object，字段兼容 `summary`、`direction`、`confidence`、`risk_notes`
- 非 JSON、坏结构、HTTPError 统一抛 `OpenAIClientError`

- [ ] **Step 6: 更新 `.env.example` 与 `dev.env`**

把 committed 配置文件更新为：

```env
GOLDFXGRAPH_DATABASE_URL=postgresql+asyncpg://goldfxgraph:change_me@localhost:5432/goldfxgraph
DATABASE_URL=
OPENAI_API_KEY=change_me
GOLDFXGRAPH_OPENAI_MODEL=gpt-5.1
GOLDFXGRAPH_OPENAI_BASE_URL=https://api.zhizengzeng.com/v1
```

保留 placeholder，不写真实 key。

- [ ] **Step 7: 重新运行测试**

Run:

```bash
uv run pytest tests/test_settings.py tests/test_openai_client.py -q
```

Expected: PASS

- [ ] **Step 8: 提交 Task 1**

```bash
git add src/goldfxgraph/packages/common/settings.py src/goldfxgraph/llm/__init__.py src/goldfxgraph/llm/openai_client.py tests/test_settings.py tests/test_openai_client.py .env.example dev.env
git commit -m "feat: add openai compatible client and config aliases"
```

### Task 2: Automatic Current Quote Discovery

**Files:**
- Modify: `src/goldfxgraph/market_data/current_quote.py`
- Modify: `tests/test_market_data.py`

- [ ] **Step 1: 写 quote discovery 失败测试**

在 `tests/test_market_data.py` 增加：

```python
def test_quote_provider_tries_multiple_sources_until_success(monkeypatch: pytest.MonkeyPatch) -> None: ...
def test_quote_provider_returns_controlled_error_when_all_sources_fail(monkeypatch: pytest.MonkeyPatch) -> None: ...
```

第一个用例应断言前一个 source 失败后会尝试下一个；第二个用例断言不会返回 mock 价格。

- [ ] **Step 2: 跑 quote 测试确认先失败**

Run:

```bash
uv run pytest tests/test_market_data.py -q
```

Expected: FAIL，提示 provider 仍要求单 URL。

- [ ] **Step 3: 实现自动 quote discovery**

在 `src/goldfxgraph/market_data/current_quote.py`：

- 保留 `CurrentQuoteProvider` 名称，但改成：

```python
class CurrentQuoteProvider:
    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        source_name: str | None = None,
        candidate_urls: list[str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None: ...
```

- 行为顺序：
  1. 若显式 `url` 存在，先尝试它
  2. 否则尝试内置 candidate URLs
  3. 任何一次成功即返回 `CurrentQuote`
  4. 全部失败后抛 `QuoteProviderError("Current quote discovery failed")`

候选源实现保持可测试，source 名称使用 host 脱敏，不暴露 query string。

- [ ] **Step 4: 保持结构化 quote 语义**

确认 `_quote_from_payload()` 仍支持：
- `price`
- `current_price`
- `close`

并统一产出 `CurrentQuote(symbol, current_price, data_source, data_timestamp)`。

- [ ] **Step 5: 重新运行 quote 测试**

Run:

```bash
uv run pytest tests/test_market_data.py -q
```

Expected: PASS

- [ ] **Step 6: 提交 Task 2**

```bash
git add src/goldfxgraph/market_data/current_quote.py tests/test_market_data.py
git commit -m "feat: add automatic current quote discovery"
```

### Task 3: Workflow And API Integration

**Files:**
- Modify: `src/goldfxgraph/workflow/nodes.py`
- Modify: `src/goldfxgraph/api/routes.py`
- Modify: `tests/test_workflow.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: 写 workflow/api 失败测试**

在 `tests/test_workflow.py` 和 `tests/test_api.py` 增加或更新测试，覆盖：

```python
def test_agent_node_uses_openai_compatible_client_when_configured() -> None: ...
def test_agent_node_falls_back_when_openai_response_is_invalid() -> None: ...
def test_create_research_run_works_without_manual_quote_url() -> None: ...
```

- [ ] **Step 2: 跑 workflow/api 测试确认先失败**

Run:

```bash
uv run pytest tests/test_workflow.py tests/test_api.py -q
```

Expected: FAIL，因为 workflow 仍依赖旧的 `agent_api_base_url` 和手工 quote URL。

- [ ] **Step 3: 在 workflow 接入 OpenAI-compatible client**

修改 `src/goldfxgraph/workflow/nodes.py`：

- `tool_fetch_current_gold_quote()` 改为默认构造新的 discovery provider
- `_remote_agent_response()` 改为优先使用：
  - `settings.openai_base_url`
  - `settings.openai_model`
  - `settings.openai_api_key`
- 若 OpenAI 配置不完整，返回 `None` 走 deterministic fallback
- 若模型返回坏结构，抛受控错误并由 agent 节点 fallback 或 API 捕获

- [ ] **Step 4: 调整 API 错误路径**

修改 `src/goldfxgraph/api/routes.py`：

- 不再把 `current_quote_url=None` 视为天然未配置错误
- 对 quote discovery 全部失败返回统一 `quote_provider_error`
- 保持失败 run 会写入 repository

- [ ] **Step 5: 重新运行 workflow/api 测试**

Run:

```bash
uv run pytest tests/test_workflow.py tests/test_api.py -q
```

Expected: PASS

- [ ] **Step 6: 提交 Task 3**

```bash
git add src/goldfxgraph/workflow/nodes.py src/goldfxgraph/api/routes.py tests/test_workflow.py tests/test_api.py
git commit -m "feat: wire openai agents and quote discovery into workflow"
```

### Task 4: Validation, Docs, And Change Tracking

**Files:**
- Modify: `openspec/changes/openai-compatible-agents-and-auto-quote-discovery/tasks.md`
- Modify: `README.md` (如已有运行说明入口)
- Modify: `docs/superpowers/specs/2026-05-23-openai-compatible-agents-and-auto-quote-discovery-design.md`（仅当实现偏离设计时）

- [ ] **Step 1: 更新运行说明**

在 `README.md` 或现有运行说明中加入：
- 后端优先支持的变量名
- `.env.example` / `dev.env` 的使用方式
- “真实 secret 不提交仓库”

- [ ] **Step 2: 勾选已完成 tasks**

把 `openspec/changes/openai-compatible-agents-and-auto-quote-discovery/tasks.md` 中完成项改为 `- [x]`。

- [ ] **Step 3: 跑完整后端校验**

Run:

```bash
uv run pytest tests/test_settings.py tests/test_openai_client.py tests/test_market_data.py tests/test_workflow.py tests/test_api.py -q
uv run ruff check .
uv run pyright src tests
openspec validate openai-compatible-agents-and-auto-quote-discovery --strict
```

Expected: 全部 PASS

- [ ] **Step 4: 复查 diff**

Run:

```bash
git diff --stat HEAD~3..
git diff -- . ':(exclude).env' ':(exclude)apps/web/node_modules'
```

确认：
- 没有真实 `OPENAI_API_KEY`
- 没有真实数据库密码被提交到示例文件
- 没有引入自动交易、券商、MCP、n8n 等超范围能力

- [ ] **Step 5: 提交 Task 4**

```bash
git add README.md openspec/changes/openai-compatible-agents-and-auto-quote-discovery/tasks.md
git commit -m "chore: finalize openai compatible agent change"
```
