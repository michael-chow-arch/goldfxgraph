## Why

GoldFXGraph 现在虽然已经把 Trading Committee 的 prompt 运行时读取接到了数据库，但仓库源码里仍然保留了完整 prompt 文本、通用 agent system prompt，以及各类外部数据源 URL。这样一来，开源仓库仍然可以直接暴露 prompt 内容和对外检索地址，不符合当前的安全与可维护性要求。

这次重构的目标是把“可变运行配置”从代码中剥离出去，让 prompt 和外部连接都通过数据库读取，并保留代码层面的最小执行逻辑。

## What Changes

- 新增数据库驱动的 prompt 读取路径，确保 agent 运行时不再依赖代码内硬编码 prompt 文本。
- 新增外部连接注册表，用数据库保存新闻、宏观、实时报价、历史日线、另类数据等外部源配置。
- 将 workflow、agent client、market data provider 和 diagnostics 调整为按 key 从数据库读取 prompt 或 source config。
- 去除代码中的默认外部 URL、默认 prompt 内容和默认 data source 常量对业务执行的依赖。
- 保留 research-only 定位，不引入自动交易、broker integration 或复杂外部编排系统。

## Impact

- 后端需要新增数据库模型与 repository/service 边界来管理 prompt 和外部连接配置。
- 现有 market data 和 agent 调用逻辑需要改为通过 registry 解析 URL、source name、headers、model metadata 等运行时配置。
- 需要补充测试，覆盖 registry 读取、缺省/缺失配置失败、以及 workflow 不再直接引用硬编码 prompt 或外部地址。
- 需要同步更新相关 OpenSpec spec delta，明确“运行时配置必须来自数据库”的契约。
