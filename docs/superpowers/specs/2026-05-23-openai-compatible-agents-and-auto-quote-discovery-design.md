## 背景

当前 GoldFXGraph 第一版已经具备 FastAPI、LangGraph、多 Agent 分析、PostgreSQL 持久化和 Vue Dashboard，但运行方式仍然依赖两类不够顺手的配置：

1. Agent 分析依赖 `GOLDFXGRAPH_AGENT_API_BASE_URL` 这一套自定义 HTTP endpoint 约定，而不是直接兼容常见的 OpenAI-compatible 接口。
2. 实时金价依赖 `GOLDFXGRAPH_CURRENT_QUOTE_URL` 由用户手工提供数据源地址，这与“系统自己完成研究输入采集”的目标不一致。

用户这次希望保留现有结构化输出与 workflow 边界，同时将后端改成能直接读取 `OPENAI_API_KEY`、`GOLDFXGRAPH_OPENAI_MODEL`、`GOLDFXGRAPH_OPENAI_BASE_URL`，并让实时金价由系统内部工具自动发现并查询。

## 设计结论

### 1. 配置兼容策略

后端 settings 增加 OpenAI-compatible 配置字段，并兼容下列变量：

- `DATABASE_URL` -> 映射为 `database_url` fallback
- `OPENAI_API_KEY` -> 映射为 `openai_api_key`
- `GOLDFXGRAPH_OPENAI_MODEL`
- `GOLDFXGRAPH_OPENAI_BASE_URL`

现有 `GOLDFXGRAPH_DATABASE_URL` 保持优先级最高，避免破坏当前部署方式。

### 2. Agent 调用方式

新增一个小型 OpenAI-compatible client 封装，负责：

- 统一拼装 base URL / model / api key
- 发送结构化 prompt
- 解析 JSON 结构化结果
- 对上层抛出稳定错误，不泄露 secret

LangGraph 中的 `agent_technical_analysis`、`agent_macro_analysis`、`agent_news_analysis`、`agent_risk_analysis` 保留现有节点名，但底层从“自定义 `/agents/{name}` endpoint”切换为直接调用 OpenAI-compatible 模型。

如果 OpenAI 配置缺失，则保留当前 deterministic fallback，确保系统仍可运行。

### 3. 实时金价策略

去掉“必须由用户提供 quote URL”的前提，改成后端内置 `quote discovery tool`：

- 优先尝试公开、无需用户 key 的候选 source
- 成功后统一转成 `CurrentQuote`
- 始终记录 `data_source` 和 `data_timestamp`
- 如果全部失败，返回受控错误并记录 research run 失败状态

为了保持第一版范围收敛，这个工具不做开放式网页搜索，也不把“查价职责”直接交给 LLM 幻觉式处理；LLM 负责分析，工具负责真实数据采集。

### 4. 测试与回归边界

需要补的回归主要有四类：

- settings 对 OpenAI / DATABASE_URL 别名的兼容测试
- OpenAI-compatible client 的请求与结构化解析测试
- 自动 quote discovery 的成功/失败测试
- API / workflow 在无手工 quote URL 条件下的回归测试

## 不做的事

- 不引入自动交易、下单或券商接入
- 不引入 MCP、n8n、多模型路由
- 不把前端改成直接调用外部模型或数据源
- 不把实时金价查询做成不可测试的“让模型自己上网搜索”

## 风险与缓解

- 公开 quote source 可能存在短时不可用  
  通过候选源顺序尝试、受控错误和测试 mock 缓解。

- OpenAI-compatible 接口返回非结构化内容  
  通过统一 client 做 JSON 解析和字段验证，失败时回退 deterministic 分析。

- 新旧配置并存可能造成优先级混淆  
  在 settings 中明确优先级：显式 `GOLDFXGRAPH_*` > OpenAI/DATABASE 别名 > 默认值。
