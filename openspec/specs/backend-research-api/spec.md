## Purpose

定义 GoldFXGraph 第一版后端研究 API 与环境配置约束，确保前端能够通过稳定、结构化、可扩展的 FastAPI 接口获取黄金研究与预测结果。

## Requirements

### Requirement: FastAPI application exposes versioned research endpoints
系统 SHALL 提供 FastAPI 应用，并在 `/api/v1` 下暴露第一版研究接口，供前端获取最新预测结果、创建研究运行、查询研究运行结果。

#### Scenario: 获取最新预测结果
- **WHEN** 前端请求 `GET /api/v1/forecast/latest`
- **THEN** 系统 MUST 返回最新已保存的结构化预测结果，或在没有预测结果时返回明确的 empty/not found 响应

#### Scenario: 创建研究运行
- **WHEN** 调用方请求 `POST /api/v1/research-runs`
- **THEN** 系统 MUST 启动一次 XAUUSD 研究 workflow，并返回本次 research run 与 forecast 的结构化结果

#### Scenario: 查询研究运行
- **WHEN** 调用方请求 `GET /api/v1/research-runs/{run_id}`
- **THEN** 系统 MUST 返回指定 research run 的状态、输入摘要、预测结果和错误信息（如有）

### Requirement: Backend configuration is environment driven
系统 SHALL 从环境变量或开发配置文件加载运行配置，并支持配置数据库 URL、XAUUSD CSV 路径、OpenAI-compatible 模型地址、模型名称和 API key，同时兼容通用环境变量别名。

#### Scenario: 加载本地开发配置
- **WHEN** 后端在本地开发环境启动
- **THEN** 系统 MUST 能从 `dev.env` 或环境变量读取 `GOLDFXGRAPH_ENV`、`GOLDFXGRAPH_LOG_LEVEL`、`GOLDFXGRAPH_DATABASE_URL`、`GOLDFXGRAPH_XAUUSD_CSV_PATH`、`GOLDFXGRAPH_OPENAI_BASE_URL`、`GOLDFXGRAPH_OPENAI_MODEL` 和 `OPENAI_API_KEY`

#### Scenario: committed 配置文件不包含真实 secret
- **WHEN** 仓库提交 `.env.example`、`dev.env` 或其他示例配置文件
- **THEN** 这些文件 MUST 只包含 placeholder 或非敏感默认值，不得提交真实 `DATABASE_URL` 密码或 `OPENAI_API_KEY`

#### Scenario: 兼容通用数据库变量
- **WHEN** 部署环境仅提供 `DATABASE_URL`
- **THEN** 系统 MUST 能将其作为 `database_url` fallback 使用，除非显式 `GOLDFXGRAPH_DATABASE_URL` 已设置

#### Scenario: 保护模型 API key
- **WHEN** API 返回配置相关错误或运行结果
- **THEN** 系统 MUST NOT 在响应、日志或前端资源中泄露真实 API key

### Requirement: API returns structured forecast contracts
系统 SHALL 使用 Pydantic models 定义 API 响应，不得只返回自由文本预测报告。

#### Scenario: 预测响应包含必要字段
- **WHEN** API 返回 forecast
- **THEN** 响应 MUST 包含当前/latest 黄金价格、数据时间、数据来源、多 Agent 摘要、最终方向、建议买入点、止盈点、止损点、风险提示、置信度、当日操作建议、长期持有建议和建议持有周期

#### Scenario: 方向字段可被前端稳定映射
- **WHEN** API 返回最终方向
- **THEN** `direction` MUST 使用 `bullish`、`bearish` 或 `neutral` 之一

### Requirement: API errors are explicit and frontend consumable
系统 SHALL 返回清晰、稳定的错误结构，便于前端展示 loading、empty、error 和 success 状态。

#### Scenario: 创建研究运行不依赖手工 quote URL
- **WHEN** 调用方请求 `POST /api/v1/research-runs`
- **THEN** 系统 MUST 在未配置手工 current quote URL 的情况下，仍尝试通过内部 quote discovery tool 完成研究流程

#### Scenario: 自动查价全部失败
- **WHEN** 内部 quote discovery tool 无法获得有效实时金价
- **THEN** API MUST 返回明确的结构化错误，并记录 research run 失败状态
