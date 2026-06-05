## Purpose

定义 GoldFXGraph 第一版真实 XAUUSD 数据读取与外部连接配置约束，确保市场数据来源、新闻源、宏观源和实时 quote 源都由数据库配置驱动，而不是散落在代码常量中。

## Requirements

### Requirement: External data sources are resolved from database-backed registry
系统 SHALL 通过数据库中的外部连接注册表解析 market data、newsflow、macro、alt-data 与 quote provider 所需的 URL、headers 和 source metadata。

#### Scenario: Source config exists in database
- **WHEN** provider 请求某个 source key
- **THEN** 系统 MUST 从数据库读取该 source 的 URL、source label 与请求元数据

#### Scenario: Source config is missing or disabled
- **WHEN** provider 请求某个 source key，但数据库未配置或该 source 被禁用
- **THEN** 系统 MUST 返回受控错误，不得回退到代码内默认外部地址

#### Scenario: External source metadata is separated from market data
- **WHEN** 系统记录外部数据抓取结果
- **THEN** 系统 MUST 将 source metadata 与 bar / indicator 数据分开保存，避免把硬编码地址混入市场数据结果
