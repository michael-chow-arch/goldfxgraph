## ADDED Requirements

### Requirement: Forecast evaluation records are persisted in PostgreSQL
系统 SHALL 将每日收盘后的 forecast evaluation 持久化到 PostgreSQL，并与对应的 research run 与 forecast 建立可追踪关联。

#### Scenario: 写入 evaluation 记录
- **WHEN** 收盘后评估任务完成某条 forecast 的分析
- **THEN** 系统 MUST 保存一条 `ForecastEvaluationModel` 记录，包含 forecast 关联、评估时间、结算口径、收益点数、命中结论和评估摘要

#### Scenario: evaluation 与 forecast 关联
- **WHEN** 系统查询某条 forecast 的历史表现
- **THEN** 系统 MUST 能通过数据库关系定位对应的 evaluation 记录

### Requirement: ORM class names include the Model suffix for evaluation entities
系统 SHALL 为新增的评估实体使用显式 SQLAlchemy ORM 类，并保持 `Model` 后缀命名风格。

#### Scenario: 定义评估 ORM
- **WHEN** 实现每日评估数据表映射
- **THEN** ORM class MUST 命名为 `ForecastEvaluationModel`

#### Scenario: 元数据注册保持显式
- **WHEN** 初始化数据库 metadata
- **THEN** 系统 MUST 通过显式导入注册 `ForecastEvaluationModel`，不得依赖 string-based dynamic imports

