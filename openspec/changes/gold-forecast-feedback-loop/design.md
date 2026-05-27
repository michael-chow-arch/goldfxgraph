## Context

GoldFXGraph 已经有基础的 forecast workflow、持久化边界和 Dashboard，但当前链路更像“单次预测输出”，而不是“持续反馈的研究系统”。这次变更要把预测、评估、反馈和可视化串成闭环，让系统在每次产生 forecast 后都保存结果，在美国市场收盘后自动复盘当日表现，并把复盘结论带回到后续预测中。

现有约束包括：

- 必须继续保持 research-only，不引入自动交易、真实下单或券商集成。
- 预测结果需要保持结构化 contract，前端必须能稳定消费。
- 数据必须可追溯，评估结论不能只存在于自由文本，而要回写数据库并可查询。
- 需要补充市场情绪与另类数据分析能力，尤其是可解释、可追踪的外部信号输入。

## Goals / Non-Goals

**Goals:**

- 每次 forecast 生成后都持久化，并和 research run 关联。
- 在美国市场收盘后自动评估当日 forecast，计算命中、盈亏点数和偏差。
- 将评估结果作为后续 forecast 的显式上下文。
- 增加市场情绪与另类数据分析 agent，覆盖像美国披萨指数这类补充信号。
- 让 Dashboard 可以展示历史 forecast、日度表现、收益点数和评估摘要图表。
- 将 `.gitignore` 过滤规则补齐，避免提交本地规范产物。

**Non-Goals:**

- 不实现自动交易、真实订单执行、券商对接或资金管理。
- 不做复杂的全量回测平台，也不把评估系统扩展成独立量化研究框架。
- 不引入多模型路由平台或复杂 observability 体系。
- 不在这个 change 中重写整个前端设计系统，只增强现有 Dashboard 的研究分析能力。

## Decisions

### 1) 采用“forecast + evaluation”双表/双模型结构

我们会把研究运行、forecast 和 evaluation 分开建模，而不是把结果全部塞进一条 forecast 记录里。forecast 负责描述“当时怎么判断”，evaluation 负责描述“事后表现如何”，这样既能保留历史预测原貌，也能独立统计胜率、收益点数和命中情况。

备选方案是把评估字段直接追加到 forecast 表中，但那会把“预测时状态”和“事后结果”混在一起，历史数据一旦重复评估就容易覆盖原始语义。双模型更适合后续做图表和反馈。

### 2) 收盘后评估使用确定性的 bar-based 规则

评估任务会在 `America/New_York` 时区的收盘后缓冲窗口执行，读取当日 forecast，并基于后续可验证的 OHLC 数据计算结果。对于 `bullish` 和 `bearish` 方向，系统会使用一致的、可重复的 bar-based 模拟规则计算是否触发 `take_profit_price` / `stop_loss_price`，以及最终的 `pnl_points`。

如果同一根 bar 同时触及 TP 和 SL，设计上采用保守规则，优先计为不利方向触发，避免过度乐观的评估。这样虽然可能略偏保守，但更适合研究场景，也更易于复现。

### 3) 将“反馈记忆”显式注入下一次 forecast

后续 forecast 不会只看最新价格和技术指标，还会加载最近若干次 evaluation 的摘要、历史命中情况和常见误差模式，作为 agent 规划阶段的上下文输入。这样能让系统从“单次推理”升级成“有记忆的研究流程”。

备选方案是只在 Dashboard 侧展示历史表现，不回流到 workflow。那样实现更简单，但无法满足“评判和分析的结论在以后预测时作为参考”的要求，所以不采用。

### 4) 新增情绪 / 另类数据 agent，并用工具节点隔离外部信号获取

market sentiment 和 pizza index 这类信号不应直接写死在 prompt 里，而应通过 tool 节点获取结构化输入，再交给 agent 做解释与归纳。这样可以保持职责清晰：工具负责采集，agent 负责分析。

我们会补上 workflow 中尚未覆盖的 agent 能力，让它们覆盖：

- market sentiment
- alternative data / pizza index
- 研究反馈摘要

如果后续发现某类信号没有稳定来源，可以先让工具返回 `unavailable` 状态，再由 agent 用其他信号降级分析，而不是用 mock 数据填充。

### 5) Dashboard 通过历史查询接口绘制表现图表

前端需要的不只是最新 forecast，还需要历史 forecast 与 evaluation 的结构化列表，用来绘制收益点数、命中率和日度表现图。后端会增加一个历史查询能力，返回按时间排序的结果集，前端再负责图表渲染与摘要展示。

备选方案是让前端自己拼装 `research-runs` 和 `forecasts` 数据，但那会把聚合逻辑散落在页面里，也不利于图表字段稳定。因此由后端提供面向 Dashboard 的聚合视图更合适。

### 6) `.gitignore` 只做本地产物过滤，不改变仓库结构

`.gitignore` 只补充本地规范产物与临时文件过滤规则，例如 `.codex/spec/` 和 `superpower` 相关目录，不会改变 OpenSpec 的目录结构或现有 change 记录方式。这能避免误提交工作流中间产物，同时不影响正式 spec 文件。

## Risks / Trade-offs

- [Risk] 收盘后评估依赖的 market bar 可能在节假日或数据延迟时不可用 → [Mitigation] 评估任务先检查可用性，不可用时写入 `skipped` 状态并保留原因。
- [Risk] TP/SL 同时触发的 bar-based 规则会和真实成交路径有差异 → [Mitigation] 采用保守且固定的规则，并在评估摘要中明确这是研究估算，不是逐笔成交回放。
- [Risk] 外部 sentiment / pizza index 数据源不稳定或成本不可控 → [Mitigation] 通过工具节点做可替换适配层，数据缺失时降级为 `unavailable`，不阻塞主流程。
- [Risk] 历史数据图表字段过多会让前端变复杂 → [Mitigation] 后端只返回 Dashboard 所需的最小聚合字段，保持响应结构稳定。

## Migration Plan

1. 先新增或扩展数据库模型与迁移路径，确保 forecast 和 evaluation 可以一对多关联，且不破坏现有 forecast 查询。
2. 再扩展 workflow，让 forecast 生成后继续写入持久化层，并把 evaluation 反馈作为后续上下文读取。
3. 增加收盘后定时任务入口，先支持手动触发，再接入正式调度。
4. 补充 Dashboard 的历史查询和图表展示，先保证结构化数据稳定，再做视觉增强。
5. 最后更新 `.gitignore`，将本地生成的 OpenSpec / superpower 临时内容排除在提交之外。

回滚时可以按相反顺序处理：先关闭定时任务，再关闭反馈读取，再回退数据库扩展，最后恢复旧 Dashboard 查询路径。

## Open Questions

- 美国市场收盘后的正式触发时间应设为 `17:30`、`18:00` 还是可配置缓冲窗口？
- pizza index 和其他另类数据信号的首批数据源应该固定哪几个？
- evaluation 结果的“盈利点数”是否采用保守 TP/SL 规则，还是以收盘价结算为默认口径？
- Dashboard 历史图表首版需要展示到什么粒度，是按天、按研究运行，还是支持时间范围筛选？
