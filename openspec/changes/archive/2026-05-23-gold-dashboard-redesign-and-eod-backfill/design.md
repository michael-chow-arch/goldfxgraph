## Context

GoldFXGraph 目前已经有可工作的 `ForecastResult`、FastAPI 前端消费层、CSV 日线加载器、CurrentQuoteProvider、OpenAI-compatible agent client，以及 LangGraph 研究 workflow。现有 Dashboard 可以展示结构化结果，但视觉风格仍偏基础；同时，日线 CSV 缺少一个自动补数机制，无法在每天收市后检测并修复缺失的 completed daily bar。

这次变更同时覆盖前端体验和后端数据维护，因此需要在不改变研究-only 边界的前提下，把“看结果”和“补数据”分成两个独立但一致的能力。

## Goals / Non-Goals

**Goals:**
- 将 Dashboard 重构为更贴近黄金研究场景的深色金融面板。
- 让最新价格、方向、置信度、OHLC、agent 摘要、风险和免责声明有明确的视觉优先级。
- 新增一个每日收市后的补数任务，自动检查 CSV 最新日期并补齐缺失日线。
- 补数过程必须使用 agent-assisted 数据查询与 deterministic validation 的组合，而不是纯 LLM 直接写盘。
- 保留现有 API 语义和研究-only 边界。

**Non-Goals:**
- 不引入自动交易、券商集成或下单执行。
- 不把补数逻辑塞进前端页面。
- 不做多模型路由、复杂观测平台或全量评估系统。
- 不强制改动现有 forecast API 的返回结构。

## Decisions

### 1) Dashboard 采用“深色研究 cockpit”而不是浅色营销式布局
选择深色 slate 背景、金色高亮、较高的信息密度和更强的数值层级，突出黄金研究场景的专业感。标题与数值使用更偏技术感的字形组合，建议沿用 `Fira Code + Fira Sans` 或同级别的技术/金融字体组合。

备选方案：
- 浅色 luxury dashboard。优点是更明亮；缺点是对大量风险、摘要和表格信息的聚焦能力较弱。
- Liquid glass / 强效果风格。优点是视觉新颖；缺点是对数据密集场景的可读性和对比度不稳定。

### 2) 收市补数使用“外部调度器 + 独立 CLI 入口”而不是长期运行的内置 scheduler
补数任务建议通过一个独立的 Python 命令入口执行，再由部署层的 cron / 容器调度在美国收市后触发。这样可以避免在应用内维持常驻调度线程，也便于本地、容器和生产环境使用同一执行路径。

备选方案：
- 在应用内加入 APScheduler。优点是自包含；缺点是会增加常驻进程、重启一致性和多实例重复触发风险。
- 使用 Celery / 队列系统。优点是扩展性强；缺点是当前项目还没有这类基础设施，代价过高。

### 3) 补数采用“agent-assisted discovery + deterministic validation”混合模式
agent 负责协助发现可用数据源、解释候选结果并给出结构化输出；真正写入 CSV 前必须经过固定规则校验，包括日期连续性、OHLC 合法性、重复数据检查和来源记录。这样可以让 agent 负责“找”和“判断”，让确定性代码负责“验”和“写”。

备选方案：
- 纯 agent 直接生成并回写数据。优点是实现快；缺点是不可控，且难以保证数据可信度。
- 纯确定性脚本只查单一数据源。优点是简单；缺点是对数据源变化和缺口修复的韧性不足。

### 4) CSV 写回采用原子更新
补数任务在写回 CSV 时应先生成临时文件，再原子替换目标文件，避免部分写入、并发中断或损坏文件。若后续需要多进程并发，文件锁可以作为增强项，但本次设计先以单任务原子写入为主。

## Risks / Trade-offs

- [Agent query latency or failure] → 通过超时、重试和受控失败处理，保证补数任务不会把错误数据写回 CSV。
- [Market close timing ambiguity] → 使用 `America/New_York` 时区并在收市后留出缓冲窗口，避免收盘瞬间数据尚未稳定。
- [CSV read/write race condition] → 通过原子写回和单任务执行约束降低风险，必要时再增加文件锁。
- [Responsive layout regression] → 在设计上坚持移动端纵向堆叠和桌面端双栏/多栏分区，避免把信息密度做得过高。
- [Scope creep into trading automation] → 明确补数任务只负责数据修复，不触发任何交易动作或外部执行。

## Migration Plan

1. 先落地 OpenSpec 变更，明确 Dashboard 视觉要求和补数任务职责边界。
2. 实现新的 Dashboard 布局与主题，但保持 API 和数据结构不变。
3. 新增补数任务的独立 CLI 入口、日期缺口检测、agent-assisted query 和 CSV 原子写回。
4. 将定时调度接到部署层，默认在美国收市后触发。
5. 增加测试覆盖后再切换到正式调度。

Rollback strategy:
- Dashboard 视觉层可以独立回滚，不影响后端研究结果。
- 补数任务可以停止调度，恢复为人工或半自动 CSV 维护，不影响现有 forecast API。

## Open Questions

- 收市触发时间是否固定为 `17:15 America/New_York`，还是需要配置成可调缓冲窗口。
- 补数时优先使用哪一组 approved historical data source，以及是否需要 fallback chain。
- 需要不需要在 CSV 层加入简单文件锁，以支持未来多实例部署。
