# GoldFXGraph

[English](README.md) | [中文](README.zh-CN.md)

GoldFXGraph is an early-stage open-source project exploring how Research Skills, Agent Harness design, and LangGraph workflows can be combined to support XAUUSD daily market research.

Phase 1 starts with one built-in Research Skill: `xauusd_daily_research`. The goal is to validate how free public data sources, tool calling, stateful workflows, data caching, fallback handling, human review, and post-forecast evaluation can be organized into a reproducible market research process.

> GoldFXGraph is not a trading system. It does not provide automated trading or investment advice. The project focuses on research workflow design, data tools, agent orchestration, and forecast evaluation.

---

## Planned Phase 1 Scope

- Built-in Research Skill: `xauusd_daily_research`
- Lightweight Agent Harness for the built-in Skill
- XAUUSD daily research workflow
- Free public data source research and integration
- XAUUSD daily price history collection
- Basic macro data collection, including U.S. Treasury yields, CPI, and Fed Funds data
- Public event calendar collection, including FOMC and CPI release schedules
- Market-related news search
- Technical indicator calculation from price history
- Function calling / tool calling
- Tool Gateway for managing data tool execution
- Input/output schemas for data tools
- LangGraph research workflow orchestration
- Schema-based research outputs
- Conditional routing by market regime
- Parallel specialist analysis steps
- Human review before saving a forecast
- Research workflow checkpointing / state persistence
- Forecast evaluation with later market data
- Research Skill evaluation record
- Tool call audit logging
- Real data caching
- Data source failure handling and fallback strategy
- Workflow progress records

> Phase 1 will not implement a full plugin-based Skill system. It will start with one or more built-in Research Skills to validate the approach.



## Future Possibilities

Future versions may explore:  

- More configurable Research Skills  
- Plugin-style Research Skills  
- Additional gold and FX research Skills  
- MCP-style Tool Server  
- Optional n8n workflow integration  
- Multi-model routing  
- More complete Tool Gateway  
- Additional data adapters  
- CFTC COT positioning data  
- More FX pairs  
- More complete forecast evaluation metrics  
- Long-term Research Skill performance tracking  
- Data source health checks  
- Scheduled research runs

---

## Disclaimer

GoldFXGraph is not a trading system.

This project does not provide financial advice, investment recommendations, trading signals, or automated execution. All outputs are generated for research, learning, and workflow exploration purposes only.

---

## Local Run And Configuration

The backend reads local configuration from `dev.env` by default. Use `.env.example` as the committed template, then keep real local values only in uncommitted env files.

Supported backend variable names:

- `GOLDFXGRAPH_ENV`
- `GOLDFXGRAPH_LOG_LEVEL`
- `GOLDFXGRAPH_DATABASE_URL`
- `DATABASE_URL` as a compatibility alias when `GOLDFXGRAPH_DATABASE_URL` is not set
- `GOLDFXGRAPH_XAUUSD_CSV_PATH`
- `GOLDFXGRAPH_CURRENT_QUOTE_URL`
- `GOLDFXGRAPH_CURRENT_QUOTE_API_KEY`
- `GOLDFXGRAPH_OPENAI_API_KEY`
- `OPENAI_API_KEY` as a compatibility alias when `GOLDFXGRAPH_OPENAI_API_KEY` is not set
- `GOLDFXGRAPH_OPENAI_MODEL`
- `GOLDFXGRAPH_OPENAI_BASE_URL`

Frontend runtime variable:

- `VITE_API_BASE_URL`

Recommended local flow:

1. Copy `.env.example` to `dev.env`.
2. Replace placeholder values such as `change_me` with local secrets.
3. Keep real API keys and database passwords out of committed files.
4. The application settings layer reads `dev.env` by default, so backend commands such as `uv run ...` will use those values when the app loads its settings.

Example:

```bash
cp .env.example dev.env
uv run pytest tests/test_settings.py -q
```

---

## License

MIT
