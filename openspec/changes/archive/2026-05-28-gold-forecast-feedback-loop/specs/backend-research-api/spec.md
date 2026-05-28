## ADDED Requirements

### Requirement: API 提供 forecast 历史与表现查询
系统 SHALL 为 Dashboard 提供可查询的历史 forecast 与 evaluation 数据接口，使前端能够绘制日度表现和收益点数图表。

#### Scenario: 查询历史 forecast 表现
- **WHEN** 前端请求 `GET /api/v1/forecast/history`
- **THEN** 系统 MUST 返回按时间排序的 forecast / evaluation 历史记录，包含方向、entry、收益点数和评估结论等结构化字段

#### Scenario: 历史数据为空
- **WHEN** 数据库中尚无历史 forecast 或 evaluation 记录
- **THEN** 系统 MUST 返回明确的 empty 语义，而不是错误或伪造数据

