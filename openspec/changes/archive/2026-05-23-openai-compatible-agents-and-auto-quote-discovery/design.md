## Context

当前仓库已经完成第一版黄金研究 workflow，并且原始 OpenSpec change 已归档。新的增量需求是让后端直接兼容 OpenAI 风格配置，并把实时金价查询从“用户提供 URL”调整为“系统内部工具自动完成”。这次变更会跨越 settings、market data、workflow 和 API 错误边界，因此需要一个小型设计文档先锁定约束。

## Goals / Non-Goals

**Goals:**
- 兼容 `DATABASE_URL` 与 OpenAI 风格配置，不破坏现有 `GOLDFXGRAPH_*` 配置
- 明确本地配置文件落点，让后端可直接按 OpenAI 风格变量运行
- 为多 Agent 节点提供直接可用的 OpenAI-compatible 调用路径
- 去除研究运行对手工 quote URL 的强依赖
- 保持结构化输出、持久化和前端 contract 稳定

**Non-Goals:**
- 不改动前端页面结构
- 不引入真实交易或经纪商能力
- 不做复杂的联网搜索代理或浏览器型 agent
- 不重写整个 LangGraph 架构

## Decisions

### 1. Settings 使用“显式项目配置优先，通用别名兜底”

优先读取 `GOLDFXGRAPH_DATABASE_URL`、`GOLDFXGRAPH_OPENAI_*`，同时接受 `DATABASE_URL`、`OPENAI_API_KEY` 作为 fallback。这样既兼容当前项目约定，也兼容用户提供的通用环境变量。

本地开发配置文件仍使用仓库根目录的 `dev.env` / `.env.example` 作为落点，但 committed 文件只能写 placeholder。真实 `DATABASE_URL` 和 `OPENAI_API_KEY` 仅写入本地未提交配置。

### 2. Agent 层新增 OpenAI-compatible client，而不是继续拼自定义 endpoint

继续使用 `/agents/{name}` 会让配置和服务协议都绑定到项目私有实现。新增 client 封装后，workflow 节点只关心“请求一个结构化分析结果”，底层则可以用 OpenAI-compatible `chat/completions` 或等价 JSON 输出能力实现。

### 3. Quote discovery tool 负责真实数据采集，LLM 不直接承担查价真实性

如果把“实时金价查询”完全交给 LLM 自己搜索，很难验证来源与时间，也不利于测试。这里继续保持工具节点边界：工具负责从多个公开可获取的候选 source 查询真实价格，agent 只消费结构化 quote 进行分析。

## Risks / Trade-offs

- [公开 quote source 可靠性有限] → 通过多候选源、受控错误和 mock 测试降低波动
- [LLM 结构化输出不稳定] → 统一 client 做 Pydantic 校验，失败时回退 deterministic 输出
- [配置兼容增加复杂度] → 明确读取顺序，并为别名映射增加单元测试
