## Purpose

定义 GoldFXGraph 第一版真实 XAUUSD 数据读取、current quote 获取与技术指标计算约束，确保研究流程建立在可验证、非 mock 的市场数据之上。

## Requirements

### Requirement: XAUUSD daily CSV loader validates real market data
系统 SHALL 从用户提供的 XAUUSD 日线 CSV 读取真实市场数据，验证必要字段，并按日期排序选择最新可用的 completed daily bar。

#### Scenario: CSV 包含必要字段
- **WHEN** CSV 文件包含 `date`、`open`、`high`、`low`、`close` 字段
- **THEN** loader MUST 解析数据、按日期升序排序，并输出 latest completed daily bar

#### Scenario: CSV 缺少必要字段
- **WHEN** CSV 文件缺少 `date`、`open`、`high`、`low` 或 `close` 任一字段
- **THEN** loader MUST 抛出可诊断的验证错误，并阻止 workflow 生成预测

#### Scenario: CSV 包含可选字段
- **WHEN** CSV 文件包含 `volume`、`source` 或 `symbol`
- **THEN** loader MUST 保留这些字段供后续分析使用

### Requirement: Current gold quote is fetched separately from daily bars
系统 SHALL 在需要 current/latest 黄金价格时，通过可配置数据源获取报价，并记录数据来源和时间，不得把 completed daily bar 与 current quote 混为一谈。

#### Scenario: Current quote provider 成功
- **WHEN** workflow 请求 current/latest XAUUSD quote 且 provider 返回有效报价
- **THEN** 系统 MUST 记录 `current_price`、`data_source` 和 `data_timestamp`

#### Scenario: Current quote provider 未配置或失败
- **WHEN** workflow 需要 current/latest quote 但 provider 不可用
- **THEN** 系统 MUST 返回明确错误或受控失败状态，不得用 mock 数据冒充真实报价

### Requirement: Technical indicators are deterministic
系统 SHALL 基于已验证日线数据计算基础技术指标，且计算过程不得调用 LLM 或依赖自由文本。

#### Scenario: 计算基础指标
- **WHEN** loader 提供足够数量的 XAUUSD 日线 bar
- **THEN** 系统 MUST 计算第一版基础指标，例如 SMA、EMA、RSI、ATR 或 MACD，并将结果结构化传递给 workflow

#### Scenario: 数据不足
- **WHEN** 日线数据不足以计算某个指标
- **THEN** 系统 MUST 在指标结果中显式标记不可用原因，而不是产生误导性数值
