# Two-Round Adversarial Trading Committee / Prompt Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不重写现有架构的前提下，把 GoldFXGraph 的最终 forecast 升级为“两轮对抗式交易委员会”仲裁流程，并把 Trading Committee 相关 prompt 全部迁移到数据库驱动的 Prompt Registry 中。

**Architecture:** 继续保留现有 specialist agents、市场数据加载、技术指标计算、持久化与 dashboard 主体结构，只在 forecast 生成链路中插入 evidence package、bull/bear 两轮辩论、chair 仲裁、规则校验与有限 repair。Prompt Registry 作为一层轻量服务挂在 persistence 之上，负责按 `prompt_key + active version` 提供英文运行 prompt 与中文维护 prompt，所有 committee agents 只消费 registry，不再硬编码完整 prompt。

**Tech Stack:** Python 3.12, FastAPI, LangGraph, Pydantic v2, SQLAlchemy async ORM, PostgreSQL, Vue 3, TypeScript, Vite, Tailwind CSS, pytest, ruff, mypy, npm。

---

### Task 1: 梳理当前契约与最小侵入点

**Files:**
- Modify: `src/goldfxgraph/workflow/graph.py`
- Modify: `src/goldfxgraph/workflow/nodes.py`
- Modify: `src/goldfxgraph/schemas/forecast.py`
- Modify: `src/goldfxgraph/persistence/models.py`
- Modify: `src/goldfxgraph/persistence/repositories.py`
- Modify: `src/goldfxgraph/api/routes.py`
- Modify: `src/goldfxgraph/api/app.py`
- Modify: `apps/web/src/types/forecast.ts`
- Modify: `apps/web/src/services/forecastApi.ts`
- Modify: `apps/web/src/pages/GoldForecastDashboard.vue`
- Test: `tests/test_workflow.py`
- Test: `tests/test_persistence.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: 先读现有测试，确认当前 contract 是怎样被断言的**

重点查看 `tests/test_workflow.py`、`tests/test_persistence.py`、`tests/test_api.py`，把当前 forecast、research run、history、scheduler 的测试边界整理出来，避免后续新增字段误伤旧行为。

- [ ] **Step 2: 标记必须保持兼容的字段与响应路径**

记录以下兼容面：`ForecastResult.direction`、`confidence_score`、`agent_votes`、`risk_notes`、`disclaimer`、`GET /api/v1/forecast/latest`、`GET /api/v1/research-runs/{run_id}`、`apps/web/src/services/forecastApi.ts` 的现有请求路径，以及 dashboard 的现有主结论布局。

- [ ] **Step 3: 确认 workflow 目前是线性汇总，哪些节点要保留**

当前 `agent_technical_analysis`、`agent_macro_analysis`、`agent_news_analysis`、`agent_market_sentiment_analysis`、`agent_alt_data_analysis`、`agent_risk_analysis`、`agent_forecast_planning` 是线性链路核心。计划保留 specialist 节点，把 `agent_forecast_planning` 降级为兼容/辅助节点或从主链路移除，但不能删除 specialist agents。

### Task 2: 新增委员会与 Prompt Registry 的 Pydantic schema

**Files:**
- Modify: `src/goldfxgraph/schemas/forecast.py`
- Test: `tests/test_workflow.py`
- Test: `tests/test_persistence.py`

- [ ] **Step 1: 设计并新增委员会输出 schema**

在 `src/goldfxgraph/schemas/forecast.py` 新增一组明确的结构体，至少包括：

```python
class EvidencePackageItem(BaseModel): ...
class EvidencePackage(BaseModel): ...
class DebateCase(BaseModel): ...
class DebateRebuttal(BaseModel): ...
class FinalDebatePosition(BaseModel): ...
class CommitteeDecision(BaseModel): ...
class DecisionValidationResult(BaseModel): ...
class LongPlan(BaseModel): ...
class ShortPlan(BaseModel): ...
class RangePlan(BaseModel): ...
class FinalForecast(BaseModel): ...
class PromptVersionMetadata(BaseModel): ...
```

其中 `FinalForecast` 要保留兼容字段，同时新增：

```python
final_bias: Literal["bullish", "bearish", "range_bound", "cautious"]
actionability: Literal["trade_candidate", "prepare_only", "observe_only", "no_trade"]
evidence_package: EvidencePackage
debate_rounds: list[...]
committee_decision: CommitteeDecision
validation_status: Literal["valid", "repaired", "failed"]
prompt_versions: list[PromptVersionMetadata]
```

- [ ] **Step 2: 让现有 `ForecastResult` 兼容新字段**

`ForecastResult` 不要立刻替换旧字段；先加可选字段，保证旧前端还能读 `direction`、`entry_price`、`take_profit_price`、`stop_loss_price`、`technical_summary` 等旧 contract。

- [ ] **Step 3: 给 `CommitteeDecision` 明确 plan 结构**

建议把 `long_plan`、`short_plan`、`range_plan`、`wait_conditions` 做成互斥可选字段，并把 `winning_side`、`adopted_arguments`、`rejected_arguments`、`validation_notes` 单独结构化，避免最终结果只靠自由文本。

### Task 3: 落地 PromptTemplateModel 与 Prompt Registry / PromptTemplateService

**Files:**
- Create: `src/goldfxgraph/persistence/prompt_registry.py`
- Modify: `src/goldfxgraph/persistence/models.py`
- Modify: `src/goldfxgraph/persistence/database.py`
- Modify: `src/goldfxgraph/persistence/repositories.py`
- Modify: `src/goldfxgraph/packages/common/settings.py`
- Test: `tests/test_persistence.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: 新增 `PromptTemplateModel`**

在 `src/goldfxgraph/persistence/models.py` 新增 `PromptTemplateModel`，字段至少包括：

```python
id, prompt_key, agent_name, node_name, prompt_type, version,
prompt_text_en, prompt_text_zh, variables_schema, output_schema_ref,
model_family, is_active, description, change_notes, created_at, updated_at
```

建议增加组合唯一约束，至少保证 `prompt_key + version` 唯一；`prompt_key + is_active` 也应保持单 active 语义。

- [ ] **Step 2: 新增 registry service**

在 `src/goldfxgraph/persistence/prompt_registry.py` 实现：

```python
get_active_prompt(prompt_key: str) -> PromptTemplateModel
validate_required_variables(template: PromptTemplateModel, variables: dict[str, Any]) -> None
render_prompt(prompt_key: str, variables: dict[str, Any]) -> RenderedPrompt
```

`RenderedPrompt` 至少包含：

```python
prompt_text_en: str
prompt_text_zh: str
prompt_key: str
prompt_version: int
rendered_variable_keys: list[str]
```

- [ ] **Step 3: 把 registry 挂到 repository 边界**

优先把 prompt registry 放在 persistence 层邻近位置，复用现有 `SessionFactory` 和 async session。不要把 prompt registry 做成一个大而全的“管理后台”，只保留运行时读取与校验。

- [ ] **Step 4: 补齐数据库初始化与迁移策略**

更新 `src/goldfxgraph/persistence/database.py`，确保 `init_models` 能创建 `prompt_templates` 表。若当前项目没有正式 migration 工具，本次用 `create_all + 必要的轻量兼容补列` 先落地，但不要把 prompt registry 放进字符串动态导入或前端资源。

### Task 4: 设计并 seed Trading Committee 的默认 prompt templates

**Files:**
- Create: `src/goldfxgraph/persistence/seed_prompt_templates.py`
- Modify: `src/goldfxgraph/persistence/database.py`
- Test: `tests/test_persistence.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: 定义 prompt_key 命名空间**

统一使用如下 key：

```text
trading_committee.bull_opening_case.system
trading_committee.bull_opening_case.user
trading_committee.bear_opening_case.system
trading_committee.bear_opening_case.user
trading_committee.bull_rebuttal.system
trading_committee.bull_rebuttal.user
trading_committee.bear_rebuttal.system
trading_committee.bear_rebuttal.user
trading_committee.bull_final_position.system
trading_committee.bull_final_position.user
trading_committee.bear_final_position.system
trading_committee.bear_final_position.user
trading_committee.chair.system
trading_committee.chair.user
trading_committee.repair.system
trading_committee.repair.user
```

- [ ] **Step 2: 设计双语 prompt 的组织方式**

每个 template 都要同时写：

- `prompt_text_en`：给 LLM 实际调用，必须是运行版英文 prompt
- `prompt_text_zh`：给维护、审查、文档展示用，中文必须忠实映射英文语义

建议每个 `prompt_key` 对应一条记录，不要把 system/user 合在一条里，以免版本和渲染边界混乱。

- [ ] **Step 3: 写 seed helper**

新增一个 seed helper，把默认 prompt 插入数据库时标记 active，并确保每个 key 只有一个 active 版本。seed 逻辑应能重复执行而不产生重复 active 行。

- [ ] **Step 4: 为 chair / repair / opening / rebuttal / final position 分别写不同语义**

不要把 prompt 写成“你是一个交易员，请自由发挥”。每个 prompt 都必须有明确职责：

- bull opening：基于 evidence package 构建最强 bullish case，并承认弱点
- bear opening：基于 evidence package 构建最强 bearish case，并承认弱点
- rebuttal：逐点回应对方 opening case，承认有效反驳，说明是否调整计划
- final position：明确是否坚持原观点，是否降级为 `prepare_only` / `observe_only` / `no_trade`
- chair：仲裁者，不是总结员，必须产出最终 bias / actionability / winning side / adopted vs rejected arguments
- repair：只修复 validation errors，不重新发明市场事实

### Task 5: 实现 committee 专用 agent 读取路径

**Files:**
- Modify: `src/goldfxgraph/workflow/nodes.py`
- Modify: `src/goldfxgraph/llm/openai_client.py`
- Modify: `src/goldfxgraph/persistence/repositories.py`
- Test: `tests/test_workflow.py`
- Test: `tests/test_openai_client.py`

- [ ] **Step 1: 抽出一个通用的 committee agent 调用助手**

建议在 `src/goldfxgraph/workflow/nodes.py` 内部或拆一个新模块，形成类似：

```python
def _invoke_committee_agent(state, prompt_key, variables, output_model) -> ParsedResult: ...
```

这个助手负责：

1. 从 Prompt Registry 读取 active template
2. 校验变量
3. 只使用 `prompt_text_en` 发送给模型
4. 记录 `prompt_key`、`prompt_version`、`rendered_variable_keys`
5. 解析结构化输出

- [ ] **Step 2: 让 `OpenAIAgentClient` 支持更严格的结构化输出**

当前 `OpenAIAgentClient` 只支持通用 `summary / direction / confidence / risk_notes`。委员会节点需要更丰富的 JSON contract，因此需要新增一个更通用的输入输出封装，但不要破坏现有 technical / macro / news / risk agent 的行为。

- [ ] **Step 3: 把 Trading Committee 四类 agent 绑到 registry**

至少实现这些 node：

```text
agent_bull_opening_case
agent_bear_opening_case
agent_bull_rebuttal
agent_bear_rebuttal
agent_bull_final_position
agent_bear_final_position
agent_trading_committee_chair
agent_repair_committee_decision
```

每个 node 的 prompt_key 必须来自 registry，不能硬编码完整 prompt 文本。

- [ ] **Step 4: 在 execution metadata 中记录版本**

每次 agent 调用都要记录：

```python
{
  "prompt_key": "...",
  "prompt_version": 3,
  "rendered_variable_keys": ["evidence_package", "bear_opening_case"],
  "agent_name": "bull_rebuttal"
}
```

不要默认写完整 rendered prompt 到日志或数据库。

### Task 6: 构建 evidence package 节点

**Files:**
- Modify: `src/goldfxgraph/workflow/nodes.py`
- Modify: `src/goldfxgraph/workflow/graph.py`
- Modify: `src/goldfxgraph/schemas/forecast.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: 把 specialist 输出统一聚合成 evidence package**

`node_build_evidence_package` 必须等待：

- technical analysis
- macro analysis
- news analysis
- market sentiment analysis
- alt data analysis
- risk analysis

全部完成后，才能将它们聚合成统一 evidence package。

- [ ] **Step 2: 规范 evidence package 内容**

至少包括：

- signal
- confidence
- key evidence
- risk factors
- invalidation conditions
- important levels
- data freshness
- tool status
- degraded source
- unavailable signals

- [ ] **Step 3: 明确 evidence package 是委员会唯一事实基础**

后续 bull / bear / chair / repair agents 只允许引用 evidence package，不允许直接去读取 specialist 原始输入后编造新事实。

### Task 7: 实现 bull / bear opening case

**Files:**
- Modify: `src/goldfxgraph/workflow/nodes.py`
- Modify: `src/goldfxgraph/workflow/graph.py`
- Modify: `src/goldfxgraph/schemas/forecast.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: 让 bull / bear opening case 并行**

在 graph 中把 `agent_bull_opening_case` 和 `agent_bear_opening_case` 设置为同一层并行依赖，二者都必须依赖 `node_build_evidence_package` 完成。

- [ ] **Step 2: bull opening case 必须是强看多论证，不是盲目看多**

输出结构至少包括：

```python
{
  "stance": "bullish",
  "summary": "...",
  "long_entry_zone": ...,
  "stop_loss_or_invalidation": ...,
  "target_zone": ...,
  "risk_reward": ...,
  "weaknesses": [...],
  "evidence_citations": [...]
}
```

同时必须在 prompt 中明确要求它承认多头弱点。

- [ ] **Step 3: bear opening case 必须是强看空论证，不是盲目看空**

同样结构，但变为 short plan，必须承认空头弱点。

- [ ] **Step 4: 两边都不得编造 evidence package 之外的市场事实**

这是高风险点，必须在 prompt 和解析后都做防线。输出里若出现 evidence package 不包含的事实，validator 或后处理必须能标记为无效。

### Task 8: 实现 bull / bear rebuttal 与 final position

**Files:**
- Modify: `src/goldfxgraph/workflow/nodes.py`
- Modify: `src/goldfxgraph/workflow/graph.py`
- Modify: `src/goldfxgraph/schemas/forecast.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: rebuttal 必须等待双方 opening case**

graph 里 `agent_bull_rebuttal` 和 `agent_bear_rebuttal` 必须在两个 opening case 都完成之后才允许执行。

- [ ] **Step 2: rebuttal 输出必须逐点回应对方**

要求输出包含：

- 反驳了对方哪些观点
- 承认了对方哪些观点
- 自己的交易计划是否需要调整
- 置信度是上升还是下降

- [ ] **Step 3: final position 必须允许 stance 降级**

`agent_bull_final_position` 和 `agent_bear_final_position` 不能被迫永远输出 trade_candidate。它们需要可以降级为：

```text
trade_candidate
prepare_only
observe_only
no_trade
```

并输出放弃该观点的条件。

- [ ] **Step 4: final position 的输出要显式关联 chair 输入**

final position 不是终局，而是 chair 仲裁前的最终立场输入，因此要结构化保留 stance、confidence、plan、abort conditions 和 key rebuttal points。

### Task 9: 实现 trading committee chair 仲裁节点

**Files:**
- Modify: `src/goldfxgraph/workflow/nodes.py`
- Modify: `src/goldfxgraph/workflow/graph.py`
- Modify: `src/goldfxgraph/schemas/forecast.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: chair 必须等待双方 final position**

`agent_trading_committee_chair` 必须在 bull / bear final position 都完成后再执行。

- [ ] **Step 2: chair 不是总结员，而是仲裁者**

prompt 和 schema 都要强制它做判断：

- 哪一方证据更强
- 哪一方更符合当前价格结构
- 哪一方风险收益比更合理
- 哪一方失效条件更清晰
- 哪一方更能解释反方证据
- 当前是否适合入场

- [ ] **Step 3: chair 输出四种 final_bias**

允许：

```text
bullish
bearish
range_bound
cautious
```

不要强制每次都给方向信号，`cautious` 与 `no_trade` 必须是正当结果。

- [ ] **Step 4: chair 输出对应 plan 结构**

如果 bullish，必须输出 `long_plan`；bearish 输出 `short_plan`; range_bound 输出 `range_plan`; cautious 输出 `wait_conditions`。

### Task 10: 实现 rule-based decision validator 与 bounded repair routing

**Files:**
- Modify: `src/goldfxgraph/workflow/nodes.py`
- Modify: `src/goldfxgraph/workflow/graph.py`
- Modify: `src/goldfxgraph/schemas/forecast.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: 在代码里做第一性规则校验**

validator 至少检查：

1. `final_bias` 只能是 `bullish/bearish/range_bound/cautious`
2. `actionability` 只能是 `trade_candidate/prepare_only/observe_only/no_trade`
3. `confidence` 必须在 0 到 1 之间
4. bullish 必须有 `long_plan`
5. bearish 必须有 `short_plan`
6. range_bound 必须有 `range_plan`
7. cautious 必须有 `wait_conditions`
8. `trade_candidate` 的 confidence 不能低于阈值，例如 0.55
9. 若存在 degraded data source，confidence 不应过高
10. long / short / range plan 的价格逻辑不能反向
11. 风险收益比过低时，不应是 trade_candidate

- [ ] **Step 2: 让 validator 输出结构化错误**

不要只抛字符串异常。建议返回可审计的 `DecisionValidationResult`，至少包含：

```python
is_valid: bool
errors: list[str]
warnings: list[str]
repairable: bool
```

- [ ] **Step 3: repair 只能做有限次**

`agent_repair_committee_decision` 只在 validator 失败且错误可修复时被调用，最多 1 到 2 次。超过次数后直接标记 failed，并停止 persistence。

- [ ] **Step 4: repair 输入必须受限**

repair prompt 只能拿到：

- validation_errors
- committee_decision
- evidence_package
- 必要的 opening / rebuttal / final position 摘要

不能让 repair agent 自由重新发明市场事实。

### Task 11: 更新 LangGraph workflow 拓扑

**Files:**
- Modify: `src/goldfxgraph/workflow/graph.py`
- Modify: `src/goldfxgraph/workflow/nodes.py`
- Modify: `src/goldfxgraph/workflow/executor.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: 把旧的 forecast planning 主链路替换成委员会链路**

主链路应变为：

1. router_validate_request
2. tool_ensure_market_data_freshness
3. tool_load_market_data
4. tool_fetch_current_gold_quote
5. tool_compute_indicators
6. specialist analysis（technical / macro / news / sentiment / alt data / risk）
7. node_build_evidence_package
8. bull/bear opening case
9. bull/bear rebuttal
10. bull/bear final position
11. agent_trading_committee_chair
12. node_validate_committee_decision
13. agent_repair_committee_decision（可选，受次数限制）
14. node_persist_forecast
15. router_finalize_result

- [ ] **Step 2: 保留 specialist agents，不删除原分析节点**

特意保留现有 technical / macro / news / sentiment / alt data / risk 节点，避免一次性大改导致回归。

- [ ] **Step 3: 处理 `agent_forecast_planning` 的去向**

如果它不再是主路径，建议将其降级为兼容辅助节点或暂时保留但不连入主 graph。不要让它再次吞掉 committee 输出。

- [ ] **Step 4: executor 的返回结果要继续向后兼容**

`run_forecast_workflow` 仍返回 `WorkflowState`，但其中 `forecast` / `result` 要能承载新的 committee-enhanced 结构。

### Task 12: 扩展持久化，保存 debate / committee decision / prompt metadata

**Files:**
- Modify: `src/goldfxgraph/persistence/models.py`
- Modify: `src/goldfxgraph/persistence/repositories.py`
- Modify: `src/goldfxgraph/persistence/database.py`
- Modify: `src/goldfxgraph/persistence/__init__.py`
- Test: `tests/test_persistence.py`
- Test: `tests/test_forecast_history_api.py`

- [ ] **Step 1: 在 `ForecastModel` 上增加 committee 结果字段**

建议新增 JSON 字段：

```python
evidence_package
debate_rounds
committee_decision
validation_status
prompt_versions
committee_metadata
```

不要创建一整套新的复杂表，除非后续查询量证明必须拆分。

- [ ] **Step 2: repository 的 save_forecast 需要把新字段一起写入**

`ForecastRepository.save_forecast` 要把最终 committee 结构一起持久化，并把 `prompt_key`、`prompt_version`、`rendered_variable_keys` 记录到 metadata 中。

- [ ] **Step 3: run 级别也要保存最小输入摘要**

`ResearchRunModel.input_summary` 保留当前输入摘要，但可以额外带上 `committee_enabled=True`、`prompt_registry_version` 之类的运行元数据。

- [ ] **Step 4: 确保失败 run 不会伪装成成功 forecast**

validation 失败并超过 repair 次数后，只能 mark run failed，不得落一条伪成功 forecast。

### Task 13: 扩展 FastAPI 响应并保持向后兼容

**Files:**
- Modify: `src/goldfxgraph/api/routes.py`
- Modify: `src/goldfxgraph/api/app.py`
- Modify: `src/goldfxgraph/schemas/forecast.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: `GET /api/v1/forecast/latest` 继续返回现有核心字段**

旧字段不能删，新增字段必须可选且 JSON 兼容。前端默认读取旧字段时不应失败。

- [ ] **Step 2: `GET /api/v1/research-runs/{run_id}` 返回 committee trace**

把：

- `evidence_package`
- `debate_rounds`
- `committee_decision`
- `validation_status`
- `prompt_versions`

都加上，同时保留 `status`、`input_summary`、`forecast`、`error_message`。

- [ ] **Step 3: `POST /api/v1/research-runs` 的行为保持兼容**

如果当前实现是通过 workflow 返回结构化结果，那么要确保新委员会结果仍符合原先调用方的预期，不要破坏创建 run 的错误处理与空结果语义。

- [ ] **Step 4: app 的 testing 模式也要跟上新 schema**

`InMemoryForecastRepository` 要模拟新增字段，否则 API 测试会断。

### Task 14: 更新 Vue types、API service 和 dashboard 展示

**Files:**
- Modify: `apps/web/src/types/forecast.ts`
- Modify: `apps/web/src/services/forecastApi.ts`
- Modify: `apps/web/src/pages/GoldForecastDashboard.vue`
- Modify: `apps/web/src/constants/forecast.ts`
- Modify: `apps/web/src/main.ts`（如样式或类型需要）
- Test: 前端当前没有专门单测时至少通过 `npm run typecheck` / `npm run build`

- [ ] **Step 1: 扩展前端类型**

在 `apps/web/src/types/forecast.ts` 新增对应 TypeScript interface，例如：

```ts
EvidencePackage
DebateCase
DebateRebuttal
FinalDebatePosition
CommitteeDecision
DecisionValidationResult
PromptVersionMetadata
LongPlan
ShortPlan
RangePlan
```

并让 `ForecastResult` 支持新增字段，但不删旧字段。

- [ ] **Step 2: service 层保持 base URL 机制不变**

`VITE_API_BASE_URL` 继续是唯一前端后端地址入口，不要把后端地址写死到 Vue 组件里。

- [ ] **Step 3: dashboard 新增委员会区域**

新增展示区：

- Evidence Package Summary
- Trading Committee Debate
- Committee Chair Decision
- Validation Status
- Prompt Version Metadata
- Graph Execution Trace

同时保持当前 hero、交易字段、agent 汇总和免责声明不被破坏。

- [ ] **Step 4: chair decision 要居中突出**

chair 区域要视觉上比 opening / rebuttal 更突出，最好作为委员会主结论卡片。range_bound 时要展示高点卖出区和低点买入区；cautious 时显示 wait conditions，不强行给入场点。

### Task 15: 增加测试覆盖

**Files:**
- Modify: `tests/test_workflow.py`
- Modify: `tests/test_persistence.py`
- Modify: `tests/test_api.py`
- Create: `tests/test_prompt_registry.py`
- Create: `tests/test_committee_validator.py`
- Create: `tests/test_committee_workflow.py`
- Create: `tests/fixtures/prompt_templates.json`（如需要）

- [ ] **Step 1: Prompt Registry 单测**

必须覆盖：

- `get_active_prompt`
- `render_prompt`
- `validate_required_variables`
- missing variable error
- inactive version 不被默认加载

- [ ] **Step 2: workflow 拓扑测试**

必须覆盖：

- opening case 等待 evidence package
- rebuttal 等待两个 opening case
- final position 等待两个 rebuttal
- chair 等待两个 final position
- validation 失败后进入 repair

- [ ] **Step 3: decision validator 测试**

必须覆盖：

- bullish requires long_plan
- bearish requires short_plan
- range_bound requires range_plan
- cautious requires wait_conditions
- confidence range validation
- low confidence trade_candidate rejection
- 风险收益比过低禁止 trade_candidate

- [ ] **Step 4: persistence / API / frontend contract 测试**

至少保证：

- 新字段能成功保存
- 旧字段仍能读取
- `GET /api/v1/forecast/latest` 不破坏空值和 404 语义
- dashboard 类型检查通过

### Task 16: 更新 README 与文档说明

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`（如果当前仓库同步维护）
- Modify: `openspec/changes/two-round-adversarial-trading-committee-prompt-registry/design.md`（如实现中有轻微偏差需同步）

- [ ] **Step 1: 简要解释 two-round committee**

更新 README 说明：

- specialist 先分析
- evidence package 再汇总
- bull / bear 两轮对抗
- chair 仲裁
- validation / repair
- final forecast 保持 research-only

- [ ] **Step 2: 说明 Prompt Registry 的维护原则**

重点写清：

- LLM 实际用 `prompt_text_en`
- `prompt_text_zh` 供审查和文档展示
- 不把 prompt 硬编码在 agent 代码里
- 不做 prompt 管理后台

### Task 17: 跑验证与修复回归

**Files:**
- 不新增文件，执行验证命令并修复失败项

- [ ] **Step 1: 后端静态检查与测试**

运行：

```bash
pytest
ruff check .
ruff format --check .
mypy .
```

- [ ] **Step 2: 前端静态检查与构建**

运行：

```bash
cd apps/web
npm install
npm run lint
npm run typecheck
npm run build
```

- [ ] **Step 3: OpenSpec 校验**

运行：

```bash
openspec validate --all
```

- [ ] **Step 4: 修复失败后再复跑**

任何 schema、API、workflow 或 dashboard 的回归都要在对应文件修复后重跑相关测试，不要跳过验证就宣称完成。

---

## Recommended Task Order

1. 先做契约梳理和 schema 设计，避免后面节点、API 和前端类型反复返工。
2. 先落地 Prompt Registry 和 prompt seed，因为委员会 agent 的所有 prompt 都依赖它。
3. 再实现 evidence package 和 workflow 拓扑，因为它决定了委员会辩论的事实边界。
4. 然后实现 bull / bear opening、rebuttal、final、chair 和 validator/repair。
5. 接着扩展 persistence 和 API，把结构化结果保存和暴露出来。
6. 最后更新 dashboard 和前端 types/service，并补齐测试与文档。

---

## File-by-file Change Plan

### `src/goldfxgraph/schemas/forecast.py`
- 新增 committee 相关 Pydantic model。
- 扩展 `ForecastResult` 与 `ResearchRunResult`，加入 committee trace、validation status、prompt versions。
- 保留旧字段兼容现有 API 和 dashboard。

### `src/goldfxgraph/persistence/models.py`
- 新增 `PromptTemplateModel`。
- 扩展 `ForecastModel`，增加 committee JSON 字段。
- 视需要为 `ResearchRunModel` 增加最小运行元数据字段，但不要拆成复杂新表。

### `src/goldfxgraph/persistence/prompt_registry.py`
- 新增 Prompt Registry / Template Service。
- 提供 active prompt 查询、变量校验、prompt 渲染、版本元数据返回。

### `src/goldfxgraph/persistence/seed_prompt_templates.py`
- 新增默认 prompt seed。
- 支持初次部署创建 active prompt。

### `src/goldfxgraph/persistence/database.py`
- 让新模型可以被 `init_models` 创建。
- 必要时补最小兼容列逻辑。

### `src/goldfxgraph/persistence/repositories.py`
- 扩展 `save_forecast` 持久化 committee 结果与 prompt metadata。
- 扩展 `get_latest_forecast` / `get_research_run` 的加载逻辑。
- 若需要，新增 prompt registry 的 repository 入口。

### `src/goldfxgraph/workflow/nodes.py`
- 新增 `node_build_evidence_package`。
- 新增 bull / bear opening、rebuttal、final position、chair、repair、validator 节点。
- 把 prompt registry 调用和结构化解析放在这里或拆出的 helper 模块中。
- 调整现有 `agent_forecast_planning` 的去向，避免其继续做最终汇总。

### `src/goldfxgraph/workflow/graph.py`
- 重排 workflow 拓扑为 committee 驱动。
- 明确依赖顺序和并行分支。

### `src/goldfxgraph/workflow/executor.py`
- 保持返回 `WorkflowState`。
- 如需补状态注入，给 committee 结构预留空间。

### `src/goldfxgraph/api/routes.py`
- 扩展 `forecast/latest` 与 `research-runs/{run_id}` 响应字段。
- 保持 404 / empty / error 语义。

### `src/goldfxgraph/api/app.py`
- 同步 testing repository 的新字段。
- 确保测试模式能返回 committee-enhanced forecast。

### `apps/web/src/types/forecast.ts`
- 扩展前端 TypeScript 类型。
- 保持旧字段不删，避免破坏旧页面逻辑。

### `apps/web/src/services/forecastApi.ts`
- 继续使用 `VITE_API_BASE_URL`。
- 对新增字段做类型化透传，不要在 service 里硬编码 prompt 相关内容。

### `apps/web/src/pages/GoldForecastDashboard.vue`
- 新增委员会展示区。
- 主结论、风险与免责声明保持原有风格。

### `tests/test_prompt_registry.py`
- 覆盖 prompt template active version、渲染、缺失变量、inactive version 不默认加载。

### `tests/test_committee_validator.py`
- 覆盖 final_bias / actionability / plan / confidence / risk-reward 校验。

### `tests/test_committee_workflow.py`
- 覆盖 workflow 依赖顺序、并行分支、repair routing、validation gating。

### `tests/test_persistence.py`
- 覆盖 prompt template seed、forecast 保存、metadata 持久化。

### `tests/test_api.py`
- 覆盖 API 兼容性、新字段返回、空值和错误语义。

---

## Prompt Template Design Plan

### 总体组织原则

1. **英文是运行版**
   - `prompt_text_en` 才能进入 LLM。
   - 句子必须简洁、明确、可约束，不要写成泛泛的“角色扮演”。

2. **中文是维护版**
   - `prompt_text_zh` 必须和英文语义一一对应。
   - 用于审查、版本 diff、文档展示，不进入模型调用。

3. **每个 prompt_key 一个职责**
   - 不要把 system、user、repair、validator 混成一个大 prompt。
   - 建议每个 key 对应一条记录，版本化升级时新增 version，而不是覆盖旧版本。

4. **严格绑定 evidence package**
   - bull / bear / chair / repair 都必须显式要求只能使用 evidence package 中的事实。
   - 不允许增加 evidence package 外的新市场事实。

### 推荐 prompt 内容框架

#### Bull Opening Case
- System:
  - 角色：华尔街黄金期货多方交易员
  - 目标：构建最强 bullish case
  - 约束：只使用 evidence package
  - 输出：结构化 JSON
  - 必须承认弱点
- User:
  - 输入 evidence package
  - 明确输出 long entry zone / invalidation / target zone / risk-reward

#### Bear Opening Case
- System:
  - 角色：华尔街黄金期货空方交易员
  - 目标：构建最强 bearish case
  - 约束：只使用 evidence package
  - 必须承认弱点
- User:
  - 输入 evidence package
  - 明确输出 short entry zone / invalidation / target zone / risk-reward

#### Rebuttal
- System:
  - 逐点回应对方 opening case
  - 必须指出哪些论点被反驳、哪些被接受、是否调整交易计划、置信度变化
  - 不得引入新事实
- User:
  - 输入 own opening、opponent opening、evidence package

#### Final Position
- System:
  - 说明是否仍坚持原 stance
  - 可以降级为 `prepare_only` / `observe_only` / `no_trade`
  - 输出最终置信度、最终计划、放弃条件
- User:
  - 输入 opening + rebuttal + evidence package

#### Chair
- System:
  - 身份是交易委员会主席 / 黄金期货交易总监
  - 必须仲裁，不是摘要员
  - 要给出 winning side、adopted/rejected arguments、final_bias、actionability、final trade plan
  - 允许 `cautious`
- User:
  - 输入 evidence package、双方 opening / rebuttal / final position

#### Repair
- System:
  - 只修复 validation errors
  - 不要重新发明市场事实
  - 只能在现有 committee output 基础上做最小修正
- User:
  - 输入 validation_errors + committee decision + evidence package

### prompt_text_en / prompt_text_zh 组织建议

- `prompt_text_en` 和 `prompt_text_zh` 都按相同 section 排列：
  - Role / Goal / Constraints / Required Output / Forbidden Behavior / Input Variables
- 两种语言的字段名保持一致，便于 diff 和审查。
- 不要在 prompt 中写任何会导致日志默认泄漏的敏感内容。

---

## Test Plan

### 1) Prompt Registry tests

文件：
- `tests/test_prompt_registry.py`
- `tests/test_persistence.py`

覆盖点：
- `get_active_prompt(prompt_key)` 返回 active version
- inactive version 不被默认加载
- `render_prompt(...)` 正确插值
- 缺失变量时报错
- `rendered_variable_keys` 正确记录

### 2) Committee workflow tests

文件：
- `tests/test_committee_workflow.py`
- `tests/test_workflow.py`

覆盖点：
- evidence package 必须等待 specialist 全部完成
- bull/bear opening case 可并行
- rebuttal 必须等待双方 opening
- final position 必须等待双方 rebuttal
- chair 必须等待双方 final position
- validation 失败后只能进入 repair 或失败

### 3) Decision validator tests

文件：
- `tests/test_committee_validator.py`
- `tests/test_workflow.py`

覆盖点：
- bullish 需要 `long_plan`
- bearish 需要 `short_plan`
- range_bound 需要 `range_plan`
- cautious 需要 `wait_conditions`
- confidence 范围必须在 0 到 1
- `trade_candidate` 低置信度必须拒绝或降级
- 风险收益比过低必须阻止 `trade_candidate`
- degraded source 下 confidence 不应过高

### 4) Persistence tests

文件：
- `tests/test_persistence.py`
- `tests/test_forecast_history_api.py`

覆盖点：
- committee 结构能保存到 `ForecastModel`
- `prompt_key` / `prompt_version` metadata 可落库
- `ResearchRunModel` 仍能保存成功 / 失败状态
- 不会伪造成功 forecast

### 5) API tests

文件：
- `tests/test_api.py`

覆盖点：
- `GET /api/v1/forecast/latest` 兼容旧字段
- `GET /api/v1/research-runs/{run_id}` 返回 committee trace
- 404 / empty / error 语义保持稳定

### 6) Frontend validation

文件：
- `apps/web/src/types/forecast.ts`
- `apps/web/src/services/forecastApi.ts`
- `apps/web/src/pages/GoldForecastDashboard.vue`

验证方式：
- `npm run typecheck`
- `npm run lint`
- `npm run build`

### 7) OpenSpec validation

命令：

```bash
openspec validate --all
```

---

## Risk Checklist

### High Risk
- Prompt Registry 初次落地时的数据库初始化与 seed 幂等性。
- committee agent 的 prompt 渲染与结构化输出解析，容易因字段不一致而失败。
- validation / repair 的分支逻辑，容易出现循环或无法落库。
- dashboard 新字段过多导致现有布局拥挤或失焦。
- `ForecastResult` 向后兼容与 `final_bias` 新语义共存时的类型混淆。

### Medium Risk
- `ForecastModel` JSON 字段变大后，查询和序列化开销增加。
- 如果 prompt 写得过于宽松，bull / bear 可能退化成普通摘要，而不是对抗式论证。
- 如果 validator 过严，可能导致过多 repair 或 failed run。

### Low Risk
- 文档同步（README / OpenSpec）工作量较小，但容易被忽略。
- 前端 service 层通常只需要类型扩展，风险低于 dashboard 页面改造。

### Mitigations
- 所有 prompt 先写单元测试，再接入 graph。
- 所有 committee 节点先用结构化 schema 约束，再对接真实 LLM。
- 先完成 validator，再接 repair。
- persistence 先 JSON 化最小字段，不要一开始就拆成多表。
- dashboard 先保留旧结构，再加委员会分区。

