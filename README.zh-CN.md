# GoldFXGraph

[English](README.md) | [中文](README.zh-CN.md)

GoldFXGraph 是一个早期准备中的开源项目，用于探索如何把 Research Skill、Agent Harness 和 LangGraph 工作流结合起来，构建面向 XAUUSD 黄金/美元日线分析的 AI 辅助研究流程。

项目第一阶段会从一个内置 Research Skill：`xauusd_daily_research` 开始，验证如何使用免费公开数据源、工具调用、状态化工作流、数据缓存、失败降级、人工审核和后续预测评估，组织一个可复现的市场研究过程。

> GoldFXGraph 不是交易系统，也不提供自动交易或投资建议。项目重点是研究流程、数据工具、Agent 工作流和预测后评估。

---

## 第一阶段计划包含内容

- 内置 Research Skill：`xauusd_daily_research`
- 面向该 Skill 的轻量 Agent Harness
- XAUUSD 黄金/美元日线研究工作流
- 免费公开数据源调研与接入Agent Skills
- XAUUSD 日线历史价格获取
- 美国国债收益率、CPI、联邦基金利率等基础宏观数据获取
- FOMC、CPI 发布时间等公开事件日历获取
- 市场相关新闻检索
- 基于历史价格的技术指标计算
- Function Calling / Tool Calling
- 轻量Tool Gateway，用于统一管理数据工具调用
- 数据工具输入/输出 Schema
- LangGraph 研究工作流编排
- Schema 化研究结果输出
- 基于市场状态的条件路由
- 多个专业分析步骤并行执行
- 预测保存前的人工审核
- 研究流程 Checkpoint / 状态保存
- 使用后续真实行情评估预测结果
- Research Skill 评估记录
- 工具调用审计日志
- 真实数据缓存
- 数据源失败处理与降级策略
- 工作流执行进度记录

> 第一阶段不会实现完整插件化 Skill 系统，而是先实现一个或多个内置 Research Skill。



## 未来可能包含内容

后续版本可能会继续探索：  

- 更可配置的 Research Skill  
- 插件化 Research Skill  
- 更多黄金与外汇研究 Skill  
- MCP-style Tool Server  
- 可选 n8n 工作流集成  
- 多模型路由  
- 更完整的 Tool Gateway  
- 更多数据适配器  
- CFTC COT 持仓数据  
- 更多外汇品种  
- 更完整的预测评估指标  
- Research Skill 长期表现统计  
- 数据源健康检查  
- 定时研究任务  

---

## 免责声明

GoldFXGraph 不是交易系统。

本项目不提供金融建议、投资建议、交易信号或自动化交易执行。所有输出仅用于研究、学习和工作流探索。

---

## License

MIT
