## Why

GoldFXGraph 目前的多智能体流程已经能产出技术、宏观、新闻、情绪、另类数据和风险分析，但最终汇总仍偏向单轮聚合式决策，缺少一个可审计、可对抗、可复盘的交易委员会决策层。与此同时，Trading Committee 相关提示词如果继续硬编码在 Python 里，会让版本追踪、审查、调整和回滚都变得困难，也不利于长期维护。

## What Changes

- 新增 **Two-Round Adversarial Trading Committee**，在 specialist agents 之后引入 evidence package、bull/bear opening case、bull/bear rebuttal、bull/bear final position、chair arbitration、validation 和 bounded repair 流程。
- 将最终 forecast 的生成从“单次聚合”升级为“委员会仲裁后输出”，并保留现有 specialist agents，不删除既有分析能力。
- 新增 **Prompt Registry / Prompt Template Management Layer**，以数据库中的 prompt template 作为 Trading Committee 相关 agents 的唯一 prompt 来源。
- 为 Trading Committee 相关 agents 同时保存英文运行版 prompt 与中文翻译 prompt，并记录 active version、prompt_key、rendered variable keys 和执行 metadata。
- 扩展持久化、API 和 Dashboard，以展示 evidence package、debate rounds、chair decision、validation status 和 prompt version metadata。
- 保持 research-only 定位，不引入自动交易、下单、broker integration、prompt 管理后台或复杂实验系统。

## Capabilities

### New Capabilities
- `two-round-adversarial-trading-committee`: 定义 evidence package、两轮对抗式辩论、chair 仲裁、规则校验、有限修复和最终结构化 forecast 输出的行为契约。
- `prompt-registry`: 定义 Trading Committee prompt template 的数据库存储、active version 读取、变量校验、变量渲染、双语 prompt 维护和执行元数据记录。

### Modified Capabilities
- `langgraph-forecast-workflow`: 将现有线性 forecast aggregation 调整为“两轮对抗式交易委员会”流程，并在 specialist analysis 之后引入 evidence package、debate、chair、validation 和 repair 节点。
- `forecast-persistence`: 扩展 research run / forecast 的持久化契约，保存 committee 过程、validation 状态、prompt version metadata 和最终 forecast 的结构化字段。
- `backend-research-api`: 在保持现有接口兼容的前提下，扩展 forecast / research run 响应以暴露 committee trace、validation status 和 prompt version metadata。
- `gold-forecast-dashboard`: 在保持当前 dashboard 风格与现有核心字段的前提下，新增 evidence package、debate rounds、chair decision、validation status 和 prompt metadata 的展示区域。

## Impact

- 后端 workflow 需要新增委员会相关节点、状态字段和验证/修复路由，但不应重写既有 specialist agents。
- 需要新增 prompt template 数据表与最小可行的 registry service，并通过 seed data / 初始化脚本提供默认 prompt 版本。
- 需要扩展 PostgreSQL 持久化以保存 committee 输出、prompt_key / prompt_version 和执行 metadata，同时避免引入全新的复杂 persistence 架构。
- FastAPI 响应需要新增字段且保持向后兼容，现有 dashboard 依赖的字段不得被破坏。
- Vue dashboard 需要新增委员会信息展示，但不引入 prompt 管理后台，也不在前端持有 prompt 内容。
- 新增测试将覆盖 prompt registry、committee 拓扑、validator 规则、repair routing、API 兼容性和 dashboard 数据契约。
