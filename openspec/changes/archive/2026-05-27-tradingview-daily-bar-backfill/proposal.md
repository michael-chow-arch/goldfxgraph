## Why

当前 GoldFXGraph 的 completed daily bars 仍然依赖运行中的后补逻辑，但补齐失败时只是记录错误，不能保证系统在启动和研究时一定建立在完整、真实的日线数据之上。用户明确要求：启动时必须先补齐日K，若补齐失败就直接报错退出；运行中跨日后也要自动补齐缺口，而且任何情况下都不能写入假数据。

## What Changes

- 在服务启动阶段加入日线补齐门禁：先检查数据库中的最新 completed daily bar，再尝试补齐到当前最新完成交易日。
- 将 completed daily bar 的补齐数据源统一为 TradingView 历史日线，不再依赖 Yahoo 历史数据作为补齐来源。
- 运行时维护任务继续在收市窗口执行，但会以数据库缺口为准补齐缺失交易日；如果补齐失败，维护流程必须显式失败。
- 在研究前增加市场数据强校验：若日线未追平，先补齐再研究；若补齐失败，研究直接失败，不生成结果。
- 明确拒绝未完成日线、推测值和任何形式的假数据写库。

## Capabilities

### Modified Capabilities
- `daily-market-data-backfill`: 日线补齐改为以数据库缺口为准、以 TradingView 历史日线为唯一补齐来源，并要求在启动时先完成补齐，否则阻止服务启动。
- `langgraph-forecast-workflow`: 研究 workflow 在生成 forecast 前必须先做市场数据强校验；若 completed daily bars 未追平，必须先触发补齐或返回受控失败。

## Impact

- 后端启动流程需要新增前置补齐检查与失败退出逻辑。
- 每日维护任务需要在启动与收市窗口都能执行同一套补齐逻辑。
- TradingView 历史日线解析与数据库 upsert 逻辑需要支持缺口补齐与异常失败。
- `research-run`、workflow 以及相关测试需要增加“数据未追平时拒绝继续”的行为验证。
