## MODIFIED Requirements

### Requirement: Backend configuration is environment driven
系统 SHALL 从环境变量或开发配置文件加载运行配置，并支持配置数据库 URL、XAUUSD CSV 路径、OpenAI-compatible 模型地址、模型名称和 API key，同时兼容通用环境变量别名。

#### Scenario: 加载本地开发配置
- **WHEN** 后端在本地开发环境启动
- **THEN** 系统 MUST 能从 `dev.env` 或环境变量读取 `GOLDFXGRAPH_ENV`、`GOLDFXGRAPH_LOG_LEVEL`、`GOLDFXGRAPH_DATABASE_URL`、`GOLDFXGRAPH_XAUUSD_CSV_PATH`、`GOLDFXGRAPH_OPENAI_BASE_URL`、`GOLDFXGRAPH_OPENAI_MODEL` 和 `OPENAI_API_KEY`

#### Scenario: 兼容通用数据库变量
- **WHEN** 部署环境仅提供 `DATABASE_URL`
- **THEN** 系统 MUST 能将其作为 `database_url` fallback 使用，除非显式 `GOLDFXGRAPH_DATABASE_URL` 已设置

#### Scenario: 保护模型 API key
- **WHEN** API 返回配置相关错误或运行结果
- **THEN** 系统 MUST NOT 在响应、日志或前端资源中泄露真实 API key

### Requirement: FastAPI application exposes versioned research endpoints
系统 SHALL 提供 FastAPI 应用，并在 `/api/v1` 下暴露第一版研究接口，供前端获取最新预测结果、创建研究运行、查询研究运行结果。

#### Scenario: 创建研究运行不依赖手工 quote URL
- **WHEN** 调用方请求 `POST /api/v1/research-runs`
- **THEN** 系统 MUST 在未配置手工 current quote URL 的情况下，仍尝试通过内部 quote discovery tool 完成研究流程

#### Scenario: 自动查价全部失败
- **WHEN** 内部 quote discovery tool 无法获得有效实时金价
- **THEN** API MUST 返回明确的结构化错误，并记录 research run 失败状态
