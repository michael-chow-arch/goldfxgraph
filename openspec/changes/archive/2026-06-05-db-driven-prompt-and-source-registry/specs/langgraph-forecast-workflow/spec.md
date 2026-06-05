## Purpose

定义 GoldFXGraph 的 LangGraph 预测工作流在执行 prompt 渲染与外部数据抓取时，必须依赖数据库配置注册表，避免任何业务关键提示词或外部检索地址出现在 workflow 代码里。

## Requirements

### Requirement: Workflow resolves prompts and source configs at runtime
系统 SHALL 在 workflow 执行时按 key 解析 prompt 与外部连接配置，并将其作为运行时依赖注入节点。

#### Scenario: Prompt and source configs are available
- **WHEN** workflow 启动
- **THEN** 系统 MUST 从数据库读取 prompt registry 与外部连接 registry，并把解析后的配置传入对应节点

#### Scenario: Runtime config is missing
- **WHEN** workflow 发现某个 prompt key 或 source key 缺失
- **THEN** 系统 MUST 终止当前 research run 并返回受控失败，不得继续使用硬编码默认值

#### Scenario: Workflow code contains no secret prompt text or source URL
- **WHEN** workflow 源码被检查
- **THEN** workflow 代码 MUST 只保留节点拓扑、key 引用和校验逻辑，不得保留完整 prompt 正文或业务外部地址常量
