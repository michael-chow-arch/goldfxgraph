## 1. 需求与契约

- [ ] 1.1 明确 Polymarket 作为公开 sentiment source 的输入与输出 contract，包括结构化市场字段、unavailable 状态和 relevance 标记。
- [ ] 1.2 设计并确认 workflow 中新增的 `tool_fetch_polymarket_inputs` 与 `agent_polymarket_analysis` 节点职责边界。

## 2. 数据采集与分析

- [ ] 2.1 实现 Polymarket 公共页面抓取与解析模块，统一从 `https://polymarket.com/zh` 读取公开市场数据。
- [ ] 2.2 为抓取结果增加与黄金相关的 relevance ranking、结构化字段标准化和不可用降级逻辑。
- [ ] 2.3 实现 `agent_polymarket_analysis`，将公开市场信号归纳为可供 forecast planning 使用的 summary、direction、confidence 和 risk notes。

## 3. Workflow 集成

- [ ] 3.1 在 `src/goldfxgraph/workflow/graph.py` 与 `src/goldfxgraph/workflow/nodes.py` 中接入 Polymarket tool / agent 节点，并保持节点命名明确。
- [ ] 3.2 将 Polymarket 输出接入现有 market sentiment 与 forecast planning 路径，确保不可用时可继续执行。
- [ ] 3.3 更新 workflow state 与相关辅助函数，确保 Polymarket 结果可以被记录、回放与测试。

## 4. 测试与验证

- [ ] 4.1 增加 Polymarket 解析 fixture、单元测试和 workflow 回归测试，覆盖成功、无相关市场和不可用三类路径。
- [ ] 4.2 运行后端相关测试与静态检查，修复 Polymarket 接入导致的回归。
- [ ] 4.3 复查 OpenSpec change 内容，确认 proposal / design / specs / tasks 与实现范围一致。
