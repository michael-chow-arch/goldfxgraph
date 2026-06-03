## ADDED Requirements

### Requirement: Forecast persistence must store committee trace, validation status and prompt version metadata
系统 SHALL 在保存 final forecast 的同时，保存 evidence package、debate rounds、chair decision、validation status 以及每个 Trading Committee agent 使用的 prompt_key / prompt_version metadata。

#### Scenario: 保存成功的 committee 结果
- **WHEN** workflow 生成并验证通过最终委员会决策
- **THEN** 系统 MUST 保存一条 forecast 记录，其中包含 evidence package、opening case、rebuttal、final position、chair decision、validation status 和 prompt version metadata

#### Scenario: 记录执行 metadata
- **WHEN** 某个 Trading Committee agent 完成一次调用
- **THEN** 系统 MUST 将该 agent 的 `prompt_key`、`prompt_version` 和渲染变量键记录到可审计的 metadata 中

#### Scenario: validation 失败
- **WHEN** committee validation 最终失败
- **THEN** 系统 MUST 保存失败状态、错误信息和已尝试的 repair 次数，但不得伪造成功 forecast

### Requirement: Prompt template persistence must remain separate from forecast persistence
系统 SHALL 通过独立的 `PromptTemplateModel` 持久化 prompt template，不得把 prompt 内容散落到 forecast 主表或前端资源中。

#### Scenario: 查询 prompt template
- **WHEN** 系统需要读取当前 active prompt
- **THEN** 它 MUST 从 prompt template 表中按 `prompt_key` 和 version 读取，而不是从 forecast 记录中回推

#### Scenario: prompt 内容变更
- **WHEN** prompt 需要升级
- **THEN** 系统 MUST 通过新增版本记录实现，而不是覆盖历史 prompt 内容
