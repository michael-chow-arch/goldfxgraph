## Context

GoldFXGraph 当前已经具备真实 XAUUSD 数据读取、技术指标计算、新闻/宏观/情绪/另类数据分析和结构化 forecast 输出能力，但最终决策仍然偏向线性聚合：各 specialist 的结论被直接汇总到单一 forecast 中，缺少明确的“多方 vs 空方”对抗过程，也缺少一个负责仲裁与失效条件判断的委员会主席层。

这次变更要解决两个相互关联的问题：

1. **决策质量与可审计性**：如果只有单轮聚合，最终预测很难解释“为什么多方赢、为什么空方输、哪条证据起了决定作用”。对研究型系统来说，这会降低复盘价值。
2. **Prompt 可维护性**：Trading Committee 相关 agents 的 prompt 一旦硬编码在 Python 代码中，版本管理、翻译维护、审查与回滚都会变得脆弱。需要一个可追踪 active version 的 registry 层。

现有约束保持不变：

- 仍然是 research-only，不做自动交易或下单。
- 不重写整个 persistence 架构，只做最小必要扩展。
- 不破坏现有 API 兼容性。
- 不在日志中默认打印完整 rendered prompt。

## Goals / Non-Goals

**Goals:**

- 将最终 forecast 改造成“两轮对抗式交易委员会”决策链，而不是单次聚合。
- 让 specialist agents 继续独立产出结构化分析结果，并先汇总成 evidence package。
- 让 bull / bear / chair / repair 相关 prompt 统一走 Prompt Registry，支持 active version 与双语维护。
- 保存 committee 运行轨迹、validation 状态与 prompt version metadata，便于审计和回放。
- 保持 `ForecastResult` 和 API 的向后兼容，现有 dashboard 字段继续可用。

**Non-Goals:**

- 不做 prompt 管理后台，不做 A/B testing，不做 prompt experiment 平台。
- 不做自动交易、策略执行、broker 接入或账户操作。
- 不把所有 reasoning 都塞进自由文本，不取消结构化模型。
- 不重构为全新的 event sourcing 或多模型路由系统。

## Decisions

### 1) 用 evidence package 作为 specialist 与 committee 之间的唯一正式接口

所有 specialist agents 仍然独立运行，但它们的输出不会直接进入最终 forecast 汇总。workflow 会先构建 `evidence_package`，再把这个 package 作为 bull / bear / chair / repair 的唯一事实基础。

这样做的原因是：

- specialist 输出与 committee 争辩解耦，便于单测和复盘
- 证据边界清晰，能防止 debate 过程中“凭空编造新事实”
- 未来如果替换某个 specialist，不会破坏 debate 层 contract

备选方案是继续让 specialist vote 直接进入最终 forecast。那样实现最简单，但会让委员会层退化成“只读摘要”，无法体现对抗式决策的价值。

### 2) 两轮辩论采用固定拓扑，而不是开放式多轮聊天

本次实现固定为 two-round debate：

- Round 1: opening case
- Round 2: rebuttal
- final position
- chair arbitration
- validation / repair

bull 和 bear 两边可以并行完成 opening case，rebuttal 必须等待双方 opening，final position 必须等待双方 rebuttal，chair 必须等待双方 final position。repair 只允许在 validator 失败后有限次触发，最多 2 次。

这样做的原因是：

- 拓扑稳定，便于测试和 UI 呈现
- 避免无限循环和自由聊天
- 让委员会层具有研究可重复性

备选方案是开放式辩论直到收敛，但那会引入不可控的 token 消耗、状态爆炸和测试不稳定，不适合第一版。

### 3) Prompt Registry 使用数据库存储的 active version，而不是文件内常量

Trading Committee 相关 agents 的 prompt 统一由 Prompt Registry 提供。每个 `prompt_key` 对应一组版本化的 prompt template，其中：

- `prompt_text_en` 用于 LLM 实际调用
- `prompt_text_zh` 用于团队审查、维护与文档展示
- `is_active` 决定默认加载的版本

agent 代码只负责：

- 读取 active prompt
- 校验变量
- 渲染 prompt
- 调用模型
- 解析结构化输出

备选方案是把 prompt 放在 YAML 文件或 Python 常量里。那会更容易启动，但会失去数据库级 versioning、active version 管理和审计追踪能力。

### 4) 用最小可行的 persistence 扩展保存 committee trace

为了避免重写 persistence 架构，本次优先复用现有 `ResearchRunModel` / `ForecastModel` 边界，在 forecast 侧增加结构化 JSON 字段来保存：

- evidence package
- debate rounds
- chair decision
- validation status
- prompt_versions / execution metadata

Prompt template 本身则单独存入 `PromptTemplateModel`。

这样做的原因是：

- 保持 one run -> one forecast 的现有边界
- 不需要新建一整套 committee event stream
- 能满足审计与 dashboard 需求

备选方案是单独建 `committee_runs`、`committee_rounds`、`agent_executions` 多张表，但这会明显扩大范围，也不符合“不要重写 persistence 架构”的约束。

### 5) 继续保留 `direction` 作为兼容字段，同时新增 `final_bias`

为了不破坏现有 dashboard 和 API 消费方，`ForecastResult` 仍保留既有字段，尤其是 `direction`。同时增加新的委员会字段：

- `final_bias`
- `actionability`
- `committee_decision`
- `validation_status`
- `prompt_versions`
- `evidence_package`
- `debate_rounds`

`direction` 用于兼容旧消费者，`final_bias` 用于表达新委员会输出的完整状态。

备选方案是直接把 `direction` 扩展到 `range_bound` / `cautious`。那会破坏现有类型约束和部分前端逻辑，不符合向后兼容要求。

### 6) Validation 以代码规则为主，Repair 只修复结构或约束违例

最终委员会结果不依赖 LLM 自行“觉得没问题”，而是由规则节点验证。validator 检查：

- 枚举值合法性
- confidence 范围
- plan 缺失与否
- 价格逻辑是否反向
- trade_candidate 是否低于阈值
- degraded data source 下 confidence 是否过高
- 风险收益比是否支撑 trade_candidate

如果验证失败，才允许调用 repair agent，且 repair 只能拿到 validation errors 与必要上下文，最多 2 次。

这样做的原因是：

- 让结构约束可测试、可解释
- 把“纠错”与“判断”分开
- 避免 LLM 在失败后继续自由发挥

备选方案是让 LLM 自审或无限重试，但那会让失败路径不可预测，也不利于稳定落库。

### 7) Dashboard 采用“主结论优先、委员会细节可展开”的布局

现有 dashboard 的核心结论区、交易字段和免责声明保持不变，只新增委员会相关区域：

- Evidence Package Summary
- Trading Committee Debate
- Committee Chair Decision
- Validation Status
- Prompt Version Metadata
- Graph Execution Trace

这样做的原因是：

- 保持当前视觉风格与信息层级
- 不让长 reasoning 淹没主结论
- 让 chair decision 居中突出

### 8) Prompt 双语维护以英文为运行版本、中文为审查版本

本次规定：

- LLM 实际调用只使用 `prompt_text_en`
- 中文 prompt 只用于审查、展示和维护，不进入模型调用
- 任何新增 prompt 版本都必须同时提供英文和中文内容

这样做的原因是：

- 运行侧保持稳定英语 prompt，降低模型解析歧义
- 维护侧保留中文说明，便于团队审查
- 版本追踪更容易做 diff 和回滚

## Risks / Trade-offs

- [Risk] Committee 过程比原先更长，token 成本和延迟会上升 → [Mitigation] 固定 two-round，限制 repair 次数，避免开放式循环。
- [Risk] Prompt Registry 增加一层数据库依赖 → [Mitigation] 提供 seed data 和清晰的 fallback 错误，避免 prompt 读取静默失败。
- [Risk] JSON 化 committee trace 可能在后期变大 → [Mitigation] 先用最小字段集，保留未来拆表的迁移空间。
- [Risk] 新的 `final_bias` 可能让前端/后端类型分叉 → [Mitigation] 保留兼容字段 `direction`，并在 API 层新增字段而不是替换字段。
- [Risk] 如果 validator 规则过严，可能导致过多 repair 或失败 → [Mitigation] 规则只校验结构和明显逻辑错误，不做主观风格评分。

## Migration Plan

1. 先新增 prompt template 表、seed 数据和 registry service，让 Trading Committee prompt 可被读取与版本化。
2. 再扩展 workflow state、委员会节点和 validator / repair 路由，保持 specialist agents 原样可用。
3. 接着扩展 persistence 与 API 响应，保存 committee trace 并保持向后兼容。
4. 最后更新 Dashboard 展示与测试，确认所有字段、状态和 prompt version metadata 能被正确展示。

回滚时优先保留 Prompt Template 表和旧字段，只关闭委员会节点与新字段消费路径即可，不需要回退整个数据库架构。

## Open Questions

- `committee trace` 先存入 `ForecastModel` 的 JSON 字段，还是未来需要单独拆成 `committee_runs` 表，取决于后续查询量与审计需求。
- `PromptTemplateModel` 的默认 seed 是否采用迁移脚本直接写入，还是通过一次性 bootstrap job 写入；本次设计倾向 migration seed，以便版本可追踪。
