## Context

GoldFXGraph 的目标是做可审计的黄金研究系统，而不是把 prompt、外部检索地址和连接参数散落在代码里。当前实现已经具备 prompt registry 的雏形，但仍存在两类硬编码：

1. prompt 文本仍以 seed 常量形式保留在 Python 文件中；
2. 外部数据源 URL、origin、referer、source label 等仍写死在 market data 模块内。

这会带来三个问题：

- 开源仓库可直接泄露模型提示词与外部检索地址；
- prompt 或 source 变更必须改代码并重新部署，无法独立演进；
- 多处模块各自维护固定字符串，后续替换数据源时容易遗漏。

## Goals / Non-Goals

**Goals:**

- 让 prompt 运行时内容只从数据库读取，代码中只保留 prompt key 和变量渲染逻辑。
- 让外部连接配置只从数据库读取，代码中不再保留业务依赖的默认 URL。
- 保持现有 workflow 拓扑、forecast contract 和 dashboard 字段不变。
- 提供清晰的缺失配置失败路径，避免静默 fallback 到硬编码地址。

**Non-Goals:**

- 不做 prompt 管理后台。
- 不做外部源的复杂调度、A/B routing 或多模型路由。
- 不重写 forecast 业务逻辑或委员会结构。

## Decisions

### 1) Prompt 只保留 key，不保留可执行正文

代码层只允许出现 prompt key、变量名、schema reference 和加载/渲染逻辑。prompt 本体必须来自数据库中的 `PromptTemplateModel`，运行时仅使用数据库中的英文 prompt。

如果需要默认 prompt，应该通过初始化种子数据或迁移脚本写入数据库，而不是把完整 prompt 文本留在 Python 常量里。

### 2) 外部连接统一抽象为 registry

新增一个用于外部连接配置的数据库模型，保存：

- source key
- source type
- url / endpoint
- headers / referer / origin / user-agent
- enabled / active 状态
- 说明与版本信息

各个 provider 通过 source key 从 registry 取配置，再执行请求。代码中不再把业务外部源 URL 当作默认值编码进去。

### 3) 运行时失败优先于隐式回退

如果某个 prompt key 或 source key 在数据库中缺失，系统应返回受控失败并记录明确错误，而不是静默回退到代码内默认值。

这样做的原因是：

- 可以尽早发现配置缺口；
- 避免仓库代码在不知不觉中成为真实运行配置的隐式来源；
- 便于审计实际使用的配置版本。

### 4) 兼容现有 workflow 和 API contract

这次重构不改变 forecast 输出结构，不改变 frontend 的核心 contract，只是把 prompt/source 解析层改成数据库驱动。

这意味着：

- workflow 节点名保持不变；
- forecast schema 保持兼容；
- 失败时仍返回结构化错误，不返回自由文本堆栈。

## Risks / Trade-offs

- [Risk] 配置缺失时更容易启动失败 → [Mitigation] 在启动校验和 health check 中尽早验证 registry 的完整性。
- [Risk] 需要一次性迁移很多硬编码字符串 → [Mitigation] 分层替换：先 prompt，再 source registry，再清理残留常量。
- [Risk] 测试需要大量 mock registry → [Mitigation] 提供轻量 repository helper 和固定测试 seed。

## Migration Plan

1. 新增外部连接 registry 数据模型与 service。
2. 把 prompt registry 的 seed 逻辑迁移到数据库驱动的初始化路径，去除代码内 prompt 正文依赖。
3. 逐个替换 market data provider 与 agent client 的硬编码 URL / prompt 文本。
4. 补充测试与启动校验，确认缺失配置会显式失败。
