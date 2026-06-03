## ADDED Requirements

### Requirement: Prompt templates must be stored in the database with bilingual content and active version metadata
系统 SHALL 通过数据库中的 `PromptTemplateModel` 存储 Trading Committee 相关 prompt template，并同时保存英文运行版 prompt 与中文翻译 prompt，以及 active version、prompt type 和版本信息。

#### Scenario: 新版本 prompt 被插入
- **WHEN** 某个 `prompt_key` 需要升级到新版本
- **THEN** 系统 MUST 允许插入新的 `PromptTemplateModel` 记录而不覆盖旧版本，并通过 `is_active` 标记当前默认版本

#### Scenario: inactive 版本存在
- **WHEN** 同一个 `prompt_key` 下存在多个版本
- **THEN** 系统 MUST 仅默认加载 active 版本，inactive 版本不得被自动选中

#### Scenario: prompt template 需要包含关键元数据
- **WHEN** 定义 prompt template
- **THEN** 记录 MUST 至少包含 `id`、`prompt_key`、`agent_name`、`node_name`、`prompt_type`、`version`、`prompt_text_en`、`prompt_text_zh`、`variables_schema`、`output_schema_ref`、`model_family`、`is_active`、`description`、`change_notes`、`created_at` 和 `updated_at`

### Requirement: Prompt Registry must load active prompt by key and render variables safely
系统 SHALL 提供 `get_active_prompt`、`validate_required_variables` 和 `render_prompt` 能力，按 `prompt_key` + active version 读取 prompt，并将变量渲染为实际发送给 LLM 的英文 prompt。

#### Scenario: 获取 active prompt
- **WHEN** agent 以 `prompt_key` 请求 prompt
- **THEN** registry MUST 返回当前 active 的 prompt template，并将 `prompt_text_en` 用于模型调用

#### Scenario: 渲染 prompt variables
- **WHEN** 变量集合满足 template 要求
- **THEN** registry MUST 渲染 prompt，并返回渲染后变量键集合供 execution metadata 记录

#### Scenario: 缺失变量
- **WHEN** 渲染时缺少必须变量
- **THEN** registry MUST 抛出可诊断错误，阻止 LLM 调用

### Requirement: Committee agent prompts must not be hardcoded in Python code
系统 SHALL 要求 Trading Committee 相关 agents 只通过 Prompt Registry 获取 prompt，而不是把完整 prompt 内容硬编码在 agent 实现里。

#### Scenario: Bull / Bear / Chair / Repair agent 执行
- **WHEN** 任一 Trading Committee agent 执行
- **THEN** agent code MUST only reference `prompt_key`、变量名和输出 schema，不得内嵌完整 prompt 文本

#### Scenario: 执行 metadata 记录
- **WHEN** prompt 被渲染并用于一次 agent 调用
- **THEN** 系统 MUST 记录 `prompt_key`、`prompt_version` 和渲染变量键，但默认不得记录完整 rendered prompt

#### Scenario: 日志输出
- **WHEN** 系统记录调试日志
- **THEN** 日志 MUST NOT 默认打印完整 rendered prompt，以避免日志过长或泄露上下文

### Requirement: Prompt Registry must support seedable default prompts for Trading Committee
系统 SHALL 允许通过 migration、初始化脚本或 seed data 预置默认 prompt 版本，使首次部署时即可启用 Trading Committee 流程。

#### Scenario: 首次部署
- **WHEN** 数据库尚未存在 Trading Committee prompt 记录
- **THEN** 系统 MUST 可以通过 seed data 创建默认 active prompt 版本

#### Scenario: 后续升级
- **WHEN** 新增 prompt 改版
- **THEN** 系统 MUST 允许新增 version 并切换 active 标记，而不是覆盖旧版内容
