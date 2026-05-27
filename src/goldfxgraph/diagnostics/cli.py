from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from goldfxgraph.diagnostics.agent_health import format_agent_health_check_report, run_agent_health_check
from goldfxgraph.packages.common.settings import load_settings
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository


def build_agent_health_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goldfxgraph agent-healthcheck")
    parser.add_argument("--env-file", type=Path, default=Path("dev.env"), help="Optional settings env file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_agent_health_parser()
    args = parser.parse_args(argv)

    settings = load_settings(env_file=args.env_file)
    return asyncio.run(_run_agent_health_check(settings=settings))


async def _run_agent_health_check(*, settings) -> int:
    session_factory = create_session_factory(str(settings.database_url))
    try:
        await init_models(session_factory.engine)
        repository = ForecastRepository(session_factory)
        report = await run_agent_health_check(settings=settings, repository=repository)
    except Exception as exc:  # noqa: BLE001
        print(f"agent-healthcheck failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await session_factory.engine.dispose()

    print(format_agent_health_check_report(report))
    return 0
