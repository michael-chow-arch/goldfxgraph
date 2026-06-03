## ADDED Requirements

### Requirement: API must expose committee-enhanced forecast contracts without breaking existing consumers
系统 SHALL 在保持现有 forecast / research run API 契约兼容的前提下，新增 committee trace、validation status 和 prompt version metadata 等字段。

#### Scenario: 获取最新 forecast
- **WHEN** 前端请求 `GET /api/v1/forecast/latest`
- **THEN** 响应 MUST 继续包含现有的核心 forecast 字段，同时新增 evidence package、debate rounds、committee decision、validation status 和 prompt version metadata

#### Scenario: 创建 research run
- **WHEN** 调用方请求 `POST /api/v1/research-runs`
- **THEN** 系统 MUST 返回一次 research run 的结构化结果，其中包含 final forecast 和 committee 相关结构化信息

#### Scenario: 查询 research run
- **WHEN** 调用方请求 `GET /api/v1/research-runs/{run_id}`
- **THEN** 系统 MUST 返回指定 run 的状态、输入摘要、forecast、committee trace、validation status、prompt version metadata 和错误信息（如有）

### Requirement: API must keep backward-compatible forecast fields while adding committee fields
系统 SHALL 保留现有字段以兼容旧前端与旧客户端，并新增能表达 committee 输出的新字段，而不是用新字段直接替换旧字段。

#### Scenario: 旧客户端只认 direction
- **WHEN** 客户端只消费既有 `direction` 字段
- **THEN** API MUST 继续返回该字段，且不得因为新增 committee 字段而改变其存在性

#### Scenario: 新客户端消费 final_bias
- **WHEN** 客户端支持 committee enhanced schema
- **THEN** API MUST 提供 `final_bias`、`actionability`、`committee_decision`、`evidence_package` 和 `prompt_versions` 等字段供前端展示
