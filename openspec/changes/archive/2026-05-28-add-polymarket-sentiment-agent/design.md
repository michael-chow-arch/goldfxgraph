## Context

GoldFXGraph 现有 workflow 已经有新闻、宏观、市场情绪和另类数据节点，但市场情绪信号还主要依赖传统资讯和静态外部信号。Polymarket 提供了公开的 prediction market 视角，可以把“市场愿意为某个宏观事件付出多少概率定价”引入研究流程，尤其适合黄金相关的通胀、利率、美元、地缘风险和风险偏好判断。

当前约束：

- 仍然必须保持 research-only，不引入自动交易、真实下单、账户接入或资金管理。
- Polymarket 只能作为公开网页信号源使用，不引入登录态、私有 API 或需要人工授权的流程。
- 结果必须保持结构化，不能把关键判断只塞进自由文本。
- 当源站不可用或页面结构变化时，workflow 不能被阻塞，必须能降级继续运行。

## Goals / Non-Goals

**Goals:**

- 为市场情绪分析增加一个 Polymarket 公开信号源。
- 让 agent 能读取与黄金有关系的公开市场概率数据，并将其归纳成结构化结论。
- 把 Polymarket 作为市场情绪链路的一部分，而不是独立的、会打断主流程的功能。
- 在源站不可用时，稳定地降级为 `unavailable`，并在 summary / risk notes 中说明原因。

**Non-Goals:**

- 不接入 Polymarket 账户登录、API key、托管交易或任何付费/私有接口。
- 不实现自动交易或基于 Polymarket 的策略执行。
- 不重做 Dashboard 的视觉结构，只在既有 market sentiment 结果中消费 Polymarket 输出。
- 不在本次变更中做大规模爬虫平台化改造。

## Decisions

### 1) 采用“独立 tool + 独立 agent”的结构，而不是塞进现有 prompt

Polymarket 会新增一个专门的数据采集节点和一个专门的分析节点。tool 负责抓取公开页面与结构化字段，agent 负责判断哪些市场与黄金最相关、这些概率变化意味着什么，以及是否需要把它解释为偏多、偏空或中性。

这样做的原因是：
- 采集逻辑和推理逻辑分离，便于测试和维护
- 页面结构变化时，只有 tool 需要调整
- agent 层可以复用同样的结构化输入做一致推理

备选方案是把 Polymarket 直接拼到 `agent_market_sentiment_analysis` 的 prompt 中，但那会让采集、筛选和解释混在一起，不利于控制失败边界，也不利于单独测试。

### 2) 只消费公开页面，入口固定为 `https://polymarket.com/zh`

Polymarket 的入口采用公开页面，不依赖登录态或专有 API。系统会从中文站入口开始抓取可见市场内容，并允许 agent 基于公开可见链接继续查看单个市场页。

这样做的原因是：
- 满足“agent 可以自由去这个网站寻找对黄金有影响的数据”的要求
- 避免私有 API / 登录态 / 账号依赖
- 可以更清晰地把不可用与页面结构变化当作正常降级路径处理

备选方案是依赖某个未验证的官方数据接口或第三方代理，但那会引入额外不稳定性，也不符合当前 research-only 与可追溯要求。

### 3) 结构化输出优先于自由文本

Polymarket tool 和 agent 都会输出结构化字段，例如：
- market title / slug / URL
- implied probability / price
- volume 或 liquidity
- close time
- relevance 标签
- unavailable 原因

然后再生成简短的中文 summary 供 forecast planning 读取。

这样做的原因是：
- 便于历史对比和单测断言
- 便于和现有 forecast / agent vote 结构对齐
- 让 `unavailable` 成为明确状态，而不是隐藏在一句文本里

### 4) 结果默认接入现有 market sentiment 链路

Polymarket 不会单独开一套前端页，也不会改变现有 Dashboard 的主结构。它的输出会作为 `market_sentiment` 的补充上下文，进入 forecast planning。

如果后续想高亮显示 Polymarket，可以复用现有 market sentiment 卡片，但这次设计不强制新增前端模块。

## Risks / Trade-offs

- [Risk] Polymarket 页面结构会变化，HTML 抓取可能失效 → [Mitigation] tool 节点返回明确的 `unavailable`，并保留最小 fallback 解析，避免阻塞 workflow。
- [Risk] 网站可能有地区/语言/反爬限制 → [Mitigation] 只使用公开页面，必要时按 `unavailable` 降级，不依赖登录态或人工介入。
- [Risk] Prediction market 信号可能与黄金并非一一对应 → [Mitigation] agent 只把它当作补充信号，最终方向仍由现有技术、宏观、新闻和风险分析共同决定。
- [Risk] 如果抓取范围过宽，可能引入噪声 → [Mitigation] 先做 relevance ranking，优先聚焦与黄金高度相关的宏观、利率、通胀、美元和地缘风险市场。

## Migration Plan

1. 先增加 Polymarket 采集与分析节点，并补齐测试 fixture，确保在本地与 CI 下可复现。
2. 再把节点接入现有 market sentiment / forecast planning 链路，确保结构化结果可被消费。
3. 最后验证当 Polymarket 不可用时，workflow 能否正确降级并继续生成 forecast。

回滚时只需要移除 Polymarket 节点与相关输入字段，现有 market sentiment / alt-data 链路可以保持不变。

## Open Questions

- Polymarket 首批应优先跟踪哪些类别：利率、通胀、美元、地缘风险，还是由 agent 自由检索后再做 relevance 排序？
- 是否需要把 Polymarket 的原始市场列表单独写入持久化，还是仅保留结构化摘要和 vote？
- 页面上是否要单独展示 Polymarket 摘要，还是先并入现有“市场情绪”卡片？
