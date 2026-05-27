## 1. 启动补齐与维护收口

- [ ] 1.1 在应用启动流程中加入 completed daily bar 补齐前置检查，补齐失败时直接阻止服务启动
- [ ] 1.2 统一启动补齐、定时维护和手动 maintenance 走同一条补齐逻辑，避免多套实现分叉
- [ ] 1.3 调整维护结果与日志，明确区分 `written`、`no-op` 与 `failed`

## 2. TradingView 历史日线补齐

- [ ] 2.1 新增或重构 TradingView 历史日线抓取器，用于按日期区间获取 completed daily bars
- [ ] 2.2 替换 Yahoo 历史补齐路径，确保缺口只从 TradingView 写入数据库
- [ ] 2.3 为未完成日线、OHLC 不合法、日期冲突和缺字段场景增加确定性校验与失败处理
- [ ] 2.4 保持数据库 upsert 幂等，并保留来源与更新时间

## 3. 研究前强校验

- [x] 3.1 在 workflow 的 market data 加载前增加 freshness preflight，复用补齐逻辑检查数据库是否追平
- [x] 3.2 当补齐失败时，让 `research-run` 和 API 返回受控错误而不是继续生成 forecast
- [x] 3.3 更新相关错误信息，明确说明是日线未追平还是 TradingView 不可用

## 4. 测试与验证

- [ ] 4.1 添加启动补齐失败阻断启动的测试
- [ ] 4.2 添加 TradingView 补齐缺口、跳过未完成日线和 no-op 的单元测试
- [x] 4.3 添加 workflow 研究前强校验测试，覆盖“日线未追平时失败”和“日线已追平时继续执行”
- [ ] 4.4 运行后端测试、ruff 和必要的启动/维护手动验证
