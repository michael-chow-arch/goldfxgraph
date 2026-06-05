from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from goldfxgraph.packages.common.settings import load_settings
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.persistence.seed_external_sources import validate_required_external_sources
from goldfxgraph.persistence.seed_prompt_templates import validate_required_prompt_templates
from goldfxgraph.workflow.executor import run_forecast_workflow


def build_research_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goldfxgraph research-run")
    parser.add_argument("--env-file", type=Path, default=Path("dev.env"), help="Optional settings env file")
    parser.add_argument(
        "--entrypoint",
        default="cli",
        help="Research run entrypoint label stored in the input summary",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_research_parser()
    args = parser.parse_args(argv)

    settings = load_settings(env_file=args.env_file)
    return asyncio.run(_run_research(settings=settings, entrypoint=args.entrypoint))


async def _run_research(*, settings, entrypoint: str) -> int:
    session_factory = create_session_factory(str(settings.database_url))
    repository = None
    run_id: int | None = None
    try:
        await init_models(session_factory.engine)
        await validate_required_prompt_templates(session_factory)
        await validate_required_external_sources(session_factory)
        repository = ForecastRepository(session_factory)
        run = await repository.create_research_run({"symbol": "XAUUSD", "entrypoint": entrypoint})
        run_id = int(run.id)
        await run_forecast_workflow(settings=settings, repository=repository, run_id=run_id)
        result_run = await repository.get_research_run(run_id)
    except Exception as exc:  # noqa: BLE001
        if repository is not None and run_id is not None:
            try:
                await repository.mark_run_failed(run_id, str(exc) or "Research run failed")
            except Exception:
                pass
        print(f"research-run failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await session_factory.engine.dispose()

    if result_run is None or result_run.forecast is None:
        print("research-run failed: forecast result missing", file=sys.stderr)
        return 1

    forecast = result_run.forecast
    print(
        "research-run success: "
        f"run_id={result_run.id} forecast_id={forecast.id} "
        f"direction={forecast.direction.value} confidence={forecast.confidence_score:.2f} "
        f"price={forecast.current_price:.2f} source={forecast.data_source}"
    )
    return 0
