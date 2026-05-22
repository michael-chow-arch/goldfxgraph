## Purpose

定义 GoldFXGraph 研究运行与结构化预测结果的 PostgreSQL 持久化边界，确保运行过程、失败状态和最终 forecast 可以被可靠查询与追踪。

## Requirements

### Requirement: Research runs are persisted in PostgreSQL
系统 SHALL 使用 PostgreSQL 保存每次研究运行记录，包括状态、输入摘要、开始时间、结束时间和错误信息（如有）。

#### Scenario: 保存成功运行
- **WHEN** `POST /api/v1/research-runs` 成功完成 workflow
- **THEN** 系统 MUST 保存一条 `ResearchRunModel` 记录，状态为成功并关联预测结果

#### Scenario: 保存失败运行
- **WHEN** workflow 因市场数据、agent 调用或持久化前置步骤失败
- **THEN** 系统 MUST 保存或更新 research run 失败状态与可诊断错误信息

### Requirement: Forecast results are persisted in PostgreSQL
系统 SHALL 使用 PostgreSQL 保存结构化预测结果，并能查询最新预测和指定 research run 的预测。

#### Scenario: 保存结构化预测
- **WHEN** workflow 生成 forecast
- **THEN** 系统 MUST 保存一条 `ForecastModel` 记录，包含价格、数据来源、方向、entry、take-profit、stop-loss、confidence、agent summaries、risk notes 和 disclaimer

#### Scenario: 查询最新预测
- **WHEN** API 处理 `GET /api/v1/forecast/latest`
- **THEN** 系统 MUST 从 PostgreSQL 返回最近保存的 `ForecastModel`

### Requirement: ORM boundaries are explicit and typed
系统 SHALL 使用 SQLAlchemy ORM，并保持 ORM class 名称带 `Model` suffix。

#### Scenario: ORM class 命名
- **WHEN** 实现 research run 与 forecast 表映射
- **THEN** ORM class MUST 命名为 `ResearchRunModel` 和 `ForecastModel`

#### Scenario: Metadata 注册
- **WHEN** 初始化数据库 metadata
- **THEN** 系统 MUST 使用显式、可维护的模型导入边界，不得依赖 string-based dynamic imports
