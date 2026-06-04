# GoldFXGraph Workflow Trace Page Override

## 页面目标

Workflow Trace Page 专门承载节点执行轨迹、prompt 版本、校验和修复信息，避免把研究主结论和执行细节混在同一页面。

## 页面信息架构

### Section 1: Trace Overview

- workflow 当前状态
- 最新运行时间
- 研究运行参考信息
- trace 是否完成

### Section 2: Execution Trace Timeline

- 节点顺序
- 每个 node 的状态
- completed / running / failed / pending

### Section 3: Prompt Versions

- prompt key
- version
- agent / node name
- prompt type

### Section 4: Validation / Repair

- validation result
- warnings
- errors
- repair status

## 页面视觉规则

- 语义上更像“运行中心”，不是“研究摘要页”。
- 时间线和状态指示必须是首要视觉。
- prompt 元数据要结构化，不要堆成普通列表。

## 页面禁忌

- 不要重复首页的研究摘要大卡片。
- 不要把行动建议放在这页当主角。
- 不要让轨迹信息失去层级，必须按步骤展示。
