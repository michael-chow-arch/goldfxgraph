## 1. 数据模型与注册表

- [x] 1.1 新增外部连接注册表的数据模型与 repository/service，支持按 `source_key` 读取外部连接配置。
- [x] 1.2 调整 prompt registry 初始化方式，确保运行时 prompt 只从数据库读取，不再依赖代码内 prompt 正文常量。

## 2. 运行时改造

- [x] 2.1 重构 agent client，让通用 system prompt 也从数据库 prompt registry 或配置表读取。
- [x] 2.2 重构 market data providers，让 TradingView、newsflow、FRED、CFTC、Polymarket、Pizza Index 等外部 URL 与请求元数据从数据库读取。
- [x] 2.3 重构 workflow / health check / startup 校验，确保缺失 registry 配置时返回受控失败而不是回退到硬编码地址。

## 3. 测试与清理

- [x] 3.1 增加 registry 与 provider 测试，覆盖数据库读取、缺失配置、禁用配置与受控失败路径。
- [x] 3.2 清理代码中不再需要的默认外部 URL、prompt 文本常量和过时配置分支。
- [x] 3.3 运行后端测试与必要的静态检查，确认重构没有破坏现有 forecast contract。
