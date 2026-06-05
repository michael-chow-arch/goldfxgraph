## Purpose

定义 GoldFXGraph 的 OpenAI-compatible agent client 必须通过数据库驱动的 prompt registry 获取运行时提示词，避免在 Python 代码中硬编码可执行 prompt 文本。

## Requirements

### Requirement: Agent prompts are loaded from database-backed registry
系统 SHALL 通过数据库中的 prompt registry 读取 agent 运行时 prompt，并只使用 prompt key、变量和 output schema 进行调用编排。

#### Scenario: Runtime prompt exists in database
- **WHEN** 某个 agent 以 prompt key 请求系统或用户 prompt
- **THEN** 系统 MUST 从数据库读取 active prompt，并将其渲染后用于模型调用

#### Scenario: Prompt text is missing from database
- **WHEN** 某个 prompt key 在数据库中不存在或未激活
- **THEN** 系统 MUST 返回受控失败，不得回退到代码内硬编码 prompt

#### Scenario: Code does not hold executable prompt text
- **WHEN** agent client 代码被审查
- **THEN** 代码 MUST 只包含 prompt key、变量名和渲染调用逻辑，不得内嵌业务可执行 prompt 正文
