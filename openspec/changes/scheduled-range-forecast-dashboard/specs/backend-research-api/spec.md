## MODIFIED Requirements

### Requirement: FastAPI application exposes versioned research endpoints
系统 SHALL 提供 FastAPI 应用，并在 `/api/v1` 下暴露第一版研究接口，供前端获取最新预测结果、查询统一调度状态和查询研究运行结果，但不得再提供手工触发研究运行的公开写入接口。

#### Scenario: 获取最新预测结果
- **WHEN** 前端请求 `GET /api/v1/forecast/latest`
- **THEN** 系统 MUST 返回最新已保存的结构化预测结果，或在没有预测结果时返回明确的 empty/not found 响应

#### Scenario: 获取最新调度状态
- **WHEN** 前端请求 `GET /api/v1/research-status/latest`
- **THEN** 系统 MUST 返回最近一次统一研究循环的执行时间、当前阶段、运行状态和各 agent 状态

#### Scenario: 查询研究运行
- **WHEN** 调用方请求 `GET /api/v1/research-runs/{run_id}`
- **THEN** 系统 MUST 返回指定 research run 的状态、输入摘要、预测结果和错误信息（如有）

#### Scenario: 不提供手工触发研究接口
- **WHEN** 调用方尝试通过公开 API 直接触发一次研究运行
- **THEN** 系统 MUST 不再暴露 `POST /api/v1/research-runs` 作为公开手工刷新入口

### Requirement: API returns structured forecast contracts
系统 SHALL 使用 Pydantic models 定义 API 响应，不得只返回自由文本预测报告。

#### Scenario: 预测响应包含必要字段
- **WHEN** API 返回 forecast
- **THEN** 响应 MUST 包含当前/latest 黄金价格、数据时间、数据来源、多 Agent 摘要、总体方向、固定时间窗口方向区间、建议买入点、止盈点、止损点、风险提示、置信度、当日操作建议、长期持有建议和建议持有周期

#### Scenario: 方向字段可被前端稳定映射
- **WHEN** API 返回最终方向
- **THEN** `direction` MUST 使用 `bullish`、`bearish` 或 `neutral` 之一

### Requirement: API errors are explicit and frontend consumable
系统 SHALL 返回清晰、稳定的错误结构，便于前端展示 loading、empty、error 和 success 状态。

#### Scenario: 最新预测不存在
- **WHEN** 调用方请求 `GET /api/v1/forecast/latest`，但数据库中尚无 forecast
- **THEN** API MUST 返回明确的 not found 或 empty 响应，且不伪造预测数据

#### Scenario: 最新调度状态尚未生成
- **WHEN** 调用方请求 `GET /api/v1/research-status/latest`，但统一调度器尚未完成过一次执行
- **THEN** API MUST 返回明确的空状态或 not found 响应，前端可以据此展示等待态

#### Scenario: 调度状态查询失败
- **WHEN** 调度状态读取过程中发生持久化或查询错误
- **THEN** API MUST 返回结构化错误，不得吞掉异常或拼接为自由文本
