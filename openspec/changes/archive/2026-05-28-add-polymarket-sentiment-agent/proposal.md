## Why

GoldFXGraph 目前已经能把新闻、宏观和另类数据纳入市场情绪分析，但还缺少一个能反映“市场对未来事件概率定价”的公开信号源。Polymarket 这类 prediction market 可以补充黄金相关的通胀、利率、地缘风险和风险偏好信号，帮助 agent 形成更前瞻的市场情绪判断。

## What Changes

- 新增一个面向 Polymarket 公开页面的数据采集与分析能力，默认从 `https://polymarket.com/zh` 读取公开内容。
- 增加一个 Polymarket sentiment agent，用于筛选与黄金相关的事件市场、提取概率与流动性等结构化信号，并归纳为可供后续 forecast 规划使用的结论。
- 将 Polymarket 作为市场情绪分析链路中的补充信号源，和现有新闻、宏观、另类数据一起进入 workflow。
- 当 Polymarket 页面不可用、结构变化或没有可用市场时，系统 SHALL 降级为 `unavailable`，但不阻塞主研究流程。
- 保持 research-only，不引入账户登录、托管身份、自动交易或任何下单行为。

## Capabilities

### New Capabilities
- `polymarket-sentiment-analysis`: 定义 Polymarket 公开页面的行情/概率采集、与黄金相关市场的筛选、结构化市场情绪分析、以及不可用时的降级行为。

### Modified Capabilities
- `langgraph-forecast-workflow`: 在现有市场情绪与另类数据链路中增加 Polymarket 数据源与 Polymarket agent，并让 forecast planning 显式消费其结构化输出。

## Impact

- 后端 workflow 需要新增 Polymarket 采集与分析节点，并把结果接入现有市场情绪与 forecast planning 路径。
- 需要新增或扩展与 public web scraping 相关的 market data 工具模块、测试 fixture 和单元测试。
- 可能需要扩展 workflow state 中的结构化输入字段，以便 agent 读取 Polymarket 结果或 unavailable 原因。
- 前端如果后续要展示 Polymarket 摘要，可以复用现有 market sentiment 区块，不需要先做视觉重构。
