## ADDED Requirements

### Requirement: Dashboard displays historical forecast performance charts
系统 SHALL 在 Dashboard 中展示历史 forecast 与 evaluation 的图表化表现，包括按预测点位计算的收益点数、命中情况和日度结论。

#### Scenario: 历史数据可用
- **WHEN** 前端通过 API 获取到历史 forecast / evaluation 数据
- **THEN** 页面 MUST 渲染按时间排序的图表，至少展示日期、direction、entry、收益点数和评估结论

#### Scenario: 支持日度表现回看
- **WHEN** 用户查看历史表现区域
- **THEN** Dashboard MUST 能清晰区分每条 forecast 的预测结果与事后 evaluation 结果

#### Scenario: 历史数据为空
- **WHEN** 后端暂时没有历史记录
- **THEN** 页面 MUST 显示明确的 empty state，而不是空白图表或误导性占位数据

