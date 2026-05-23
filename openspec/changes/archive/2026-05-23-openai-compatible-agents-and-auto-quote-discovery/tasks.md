## 1. 配置与客户端边界

- [x] 1.1 扩展 `settings.py`，兼容 `DATABASE_URL`、`OPENAI_API_KEY`、`GOLDFXGRAPH_OPENAI_MODEL`、`GOLDFXGRAPH_OPENAI_BASE_URL`
- [x] 1.2 更新 `.env.example` 与 `dev.env` 的变量约定，确保 committed 文件仅保留 placeholder，同时支持本地真实值按 OpenAI 风格配置运行
- [x] 1.3 新增 OpenAI-compatible agent client 封装，并定义结构化请求/响应边界
- [x] 1.4 为配置映射与 client 行为补充单元测试

## 2. 自动实时金价获取

- [x] 2.1 重构 `CurrentQuoteProvider` 为自动 quote discovery 模式，支持候选 source 顺序尝试
- [x] 2.2 保留 `CurrentQuote` 结构化返回与 `data_source`、`data_timestamp` 记录
- [x] 2.3 为自动查价成功、全部失败和错误脱敏补充测试

## 3. Workflow 与 API 接入

- [x] 3.1 将技术、宏观、新闻、风险 agent 节点切换为优先调用 OpenAI-compatible client
- [x] 3.2 在模型不可用或响应无效时保留 deterministic fallback 或受控错误
- [x] 3.3 更新 API / workflow 测试，覆盖无手工 quote URL 时的研究运行路径

## 4. 验证与收尾

- [x] 4.1 运行相关后端测试与静态检查
- [x] 4.2 更新必要文档与本地运行说明，明确新的环境变量约定
- [x] 4.3 复查 diff，确认未提交 secret、未扩大 scope
