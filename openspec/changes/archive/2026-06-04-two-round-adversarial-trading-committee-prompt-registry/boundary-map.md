# Trading Committee 边界地图

本文档用于给后续实现任务提供一个稳定的边界参考：哪些内容必须通过新的 spec delta 明确约束，哪些内容只是实现层扩展，且不需要再扩大 spec 范围。

## 现有稳定边界

当前仓库里，committee 相关能力会落在以下现有边界上：

- **Schema 边界**：`src/goldfxgraph/schemas/forecast.py`
  - 现有 `ForecastResult`、`AgentVote`、`ForecastWindowDirection` 已经定义了当前线性 forecast 的结构化输出。
  - committee 方案会新增自己的结构化 schema，但不能直接破坏现有 `ForecastResult` 的兼容字段。

- **Workflow 边界**：`src/goldfxgraph/workflow/nodes.py` 与 `src/goldfxgraph/workflow/graph.py`
  - 当前 graph 还是线性链路：specialist 分析 -> risk -> forecast planning -> persist。
  - committee 方案需要在这个边界内插入新的节点和路由，但不会删除现有 specialist agent。

- **Persistence 边界**：`src/goldfxgraph/persistence/models.py` 与 `src/goldfxgraph/persistence/repositories.py`
  - 当前持久化边界只覆盖 `ResearchRunModel`、`ForecastModel`、`ForecastEvaluationModel`。
  - committee trace、prompt metadata 与 validation 状态要么落到现有 forecast/run 边界的扩展字段里，要么通过新增的 prompt template 存储边界承载。

- **API 边界**：`src/goldfxgraph/api/routes.py`
  - 当前对外公共 API 只有 `/forecast/latest`、`/forecast/history`、`/research-status/latest`、`/research-runs/{run_id}`、`/market-data/bars`。
  - committee 方案不能先改路由形状；只能在既有响应模型上增加兼容字段。

- **前端服务边界**：`apps/web/src/services/forecastApi.ts` 与 `apps/web/src/types/forecast.ts`
  - 前端已经通过 typed service 消费后端 forecast。
  - committee 方案需要扩展类型和展示层，但不能把 prompt 内容搬到前端。

- **Dashboard 边界**：`apps/web/src/pages/GoldForecastDashboard.vue`
  - 当前页面只负责展示最新 forecast、history 和调度状态。
  - committee 方案要新增展示区块，但不能改成 prompt 管理后台，也不能破坏现有首屏主结论层级。

## 必须新增 spec delta 的能力

以下能力属于“契约新增”或“对外语义改变”，后续实现前必须由 spec delta 先定住：

1. **Two-Round Adversarial Trading Committee**
   - 需要新的 workflow 语义：evidence package、opening case、rebuttal、final position、chair arbitration、validation、bounded repair。
   - 需要新的节点拓扑要求和失败约束。
   - 归属：`openspec/changes/two-round-adversarial-trading-committee-prompt-registry/specs/langgraph-forecast-workflow/spec.md`

2. **Prompt Registry**
   - 需要数据库化 prompt template、active version、双语 prompt、变量校验与渲染规则。
   - 需要明确 committee prompts 不能 hardcode 在 Python agent 代码里。
   - 归属：`openspec/changes/two-round-adversarial-trading-committee-prompt-registry/specs/prompt-registry/spec.md`

3. **Forecast / research run 持久化语义扩展**
   - 需要明确 committee trace、validation status、prompt version metadata、evidence package 等是否属于 forecast 记录的结构化扩展。
   - 需要明确 `ForecastModel` / `ResearchRunModel` 的兼容边界。
   - 归属：`openspec/changes/two-round-adversarial-trading-committee-prompt-registry/specs/forecast-persistence/spec.md`

4. **Backend public API contract 扩展**
   - 需要明确 `GET /api/v1/forecast/latest` 和 `GET /api/v1/research-runs/{run_id}` 是否新增 committee trace、validation status、prompt metadata 等字段。
   - 需要明确旧字段继续保留，不做破坏性替换。
   - 归属：`openspec/changes/two-round-adversarial-trading-committee-prompt-registry/specs/backend-research-api/spec.md`

5. **Dashboard 展示契约扩展**
   - 需要明确新的展示区域有哪些，以及主结论区如何保持稳定。
   - 归属：`openspec/changes/two-round-adversarial-trading-committee-prompt-registry/specs/gold-forecast-dashboard/spec.md`

## 只需实现层扩展的能力

以下内容不需要新增对外 spec 语义，只要在实现层满足上面的 spec delta 即可：

- **Pydantic 实现文件拆分**
  - 新增 `committee` 相关 schema 文件、辅助 validator、输出转换器，属于实现组织方式。
  - 只要最终结构满足 spec，不需要单独再开一个 spec delta。

- **Prompt Registry 服务实现**
  - `get_active_prompt`、`validate_required_variables`、`render_prompt` 的具体 Python 服务实现、缓存策略、查询实现细节，属于实现层。
  - spec 只需要约束外部行为，不需要约束内部类名和模块名。

- **Repository 方法扩展**
  - 在 `ForecastRepository` 上新增用于 committee trace / prompt metadata 的写入与读取方法，属于实现层边界扩展。
  - 只要不改变既有公开 API 的兼容行为，就不需要再额外开 spec。

- **Graph 节点编排细节**
  - 具体用几个 helper、是否拆分 tool/agent wrapper、如何组装 state，是实现层问题。
  - spec 只需要约束拓扑和修复上限，不需要规定每个 helper 文件。

- **前端组件拆分**
  - dashboard 的卡片、折叠区、标签、时间线组件如何拆分，属于实现层。
  - spec 只需要约束展示内容、层级和不破坏现有布局。

## 不建议新增 spec delta 的内容

以下内容如果后续被单独提出来，通常会造成过度约束，因此先不纳入新 spec：

- prompt template 的具体文案内容
- 每个 agent 的 prompt 变量拼接顺序
- repair prompt 的 exact wording
- 某个具体 committee trace JSON 的所有内部字段名
- 前端组件的具体 class 名称
- repository 内部 SQL 查询写法

这些都应该留在实现层，只要最终外部 contract 与行为满足 spec 即可。

## 给后续任务的落点

后续实现任务可以直接依赖下面这个分界：

- **先由 spec delta 定义行为**
  - committee workflow 拓扑
  - prompt registry contract
  - persistence / API / dashboard 的新增字段语义

- **再由实现层补细节**
  - schema、repository、nodes、service、Vue 组件
  - prompt seed、rendering、validation、serialization

这样可以保证下一步实现时，既不会把 prompt 和 runtime 细节提前写死，也不会把委员会行为扩散成无法测试的隐式约定。
