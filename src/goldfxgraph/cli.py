from __future__ import annotations

import sys

from goldfxgraph.backfill.cli import evaluate_main, maintenance_main
from goldfxgraph.backfill.cli import main as backfill_main
from goldfxgraph.diagnostics.cli import main as agent_healthcheck_main
from goldfxgraph.market_data import ingest as market_data_ingest
from goldfxgraph.research.cli import main as research_run_main


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(
            "Usage: goldfxgraph backfill|evaluate|maintenance|agent-healthcheck|research-run|"
            "import-market-data|ingest-market-data [options]"
        )
        return 0

    command, *rest = args
    if command == "backfill":
        return backfill_main(rest)
    if command == "evaluate":
        return evaluate_main(rest)
    if command in {"maintenance", "maintain", "eod-maintenance"}:
        return maintenance_main(rest)
    if command in {"agent-healthcheck", "healthcheck", "agent-health-check"}:
        return agent_healthcheck_main(rest)
    if command in {"research-run", "run-research", "research"}:
        return research_run_main(rest)
    if command in {"import-market-data", "ingest-market-data"}:
        return market_data_ingest.main(rest)

    print(f"Unknown command: {command}")
    print(
        "Usage: goldfxgraph backfill|evaluate|maintenance|agent-healthcheck|research-run|"
        "import-market-data|ingest-market-data [options]"
    )
    return 1
