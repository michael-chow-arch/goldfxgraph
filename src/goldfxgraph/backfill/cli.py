from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from goldfxgraph.backfill.eod_backfill import BackfillResult, run_eod_backfill
from goldfxgraph.backfill.eod_evaluation import run_eod_forecast_evaluation
from goldfxgraph.backfill.maintenance import run_eod_maintenance
from goldfxgraph.packages.common.settings import GoldFXGraphSettings, load_settings
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository


def build_backfill_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goldfxgraph backfill")
    parser.add_argument("--as-of", dest="as_of", default=None, help="Optional ISO timestamp for deterministic runs")
    parser.add_argument("--env-file", type=Path, default=Path("dev.env"), help="Optional settings env file")
    return parser


def build_evaluation_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goldfxgraph evaluate")
    parser.add_argument("--as-of", dest="as_of", default=None, help="Optional ISO timestamp for deterministic runs")
    parser.add_argument("--env-file", type=Path, default=Path("dev.env"), help="Optional settings env file")
    return parser


def build_maintenance_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goldfxgraph maintenance")
    parser.add_argument("--as-of", dest="as_of", default=None, help="Optional ISO timestamp for deterministic runs")
    parser.add_argument("--env-file", type=Path, default=Path("dev.env"), help="Optional settings env file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_backfill_parser()
    args = parser.parse_args(argv)

    settings = load_settings(env_file=args.env_file)
    now = _parse_now(args.as_of)

    try:
        result = asyncio.run(_run_backfill(settings=settings, now=now))
    except Exception as exc:  # noqa: BLE001
        print(f"backfill failed: {exc}", file=sys.stderr)
        return 1

    status = result.status
    missing = ",".join(item.isoformat() for item in result.missing_dates) or "-"
    target_date = getattr(result, "target_date", None)
    print(f"backfill {status}: latest={result.latest_existing_date} target={target_date} missing={missing}")
    return 1 if status == "failed" else 0


def evaluate_main(argv: list[str] | None = None) -> int:
    parser = build_evaluation_parser()
    args = parser.parse_args(argv)

    settings = load_settings(env_file=args.env_file)
    now = _parse_now(args.as_of)
    return asyncio.run(_run_evaluation(settings=settings, now=now))


def maintenance_main(argv: list[str] | None = None) -> int:
    parser = build_maintenance_parser()
    args = parser.parse_args(argv)

    settings = load_settings(env_file=args.env_file)
    now = _parse_now(args.as_of)
    return asyncio.run(_run_maintenance(settings=settings, now=now))


def _parse_now(as_of: str | None) -> datetime:
    now = datetime.fromisoformat(as_of) if as_of else datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now


async def _run_evaluation(
    *,
    settings: GoldFXGraphSettings,
    now: datetime,
) -> int:
    session_factory = create_session_factory(str(settings.database_url))
    try:
        await init_models(session_factory.engine)
        repository = ForecastRepository(session_factory)
        result = await run_eod_forecast_evaluation(
            settings=settings,
            repository=repository,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"evaluation failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await session_factory.engine.dispose()

    print(
        "evaluation "
        f"{result.status}: target={result.target_date} "
        f"settlement={result.settlement_bar_date} "
        f"evaluated={','.join(str(item) for item in result.evaluated_forecast_ids) or '-'} "
        f"skipped={','.join(str(item) for item in result.skipped_forecast_ids) or '-'}"
    )
    return 0


async def _run_backfill(*, settings: GoldFXGraphSettings, now: datetime) -> BackfillResult:
    session_factory = create_session_factory(str(settings.database_url))
    try:
        await init_models(session_factory.engine)
        repository = ForecastRepository(session_factory)
        result = await run_eod_backfill(
            settings=settings,
            repository=repository,
            now=now,
        )
    finally:
        await session_factory.engine.dispose()

    return result


async def _run_maintenance(
    *,
    settings: GoldFXGraphSettings,
    now: datetime,
) -> int:
    session_factory = create_session_factory(str(settings.database_url))
    try:
        await init_models(session_factory.engine)
        repository = ForecastRepository(session_factory)
        result = await run_eod_maintenance(
            settings=settings,
            repository=repository,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"maintenance failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await session_factory.engine.dispose()

    print(
        "maintenance "
        f"{result.status}: "
        f"backfill={result.backfill.status} "
        f"evaluation={result.evaluation.status} "
        f"latest_db={result.backfill.latest_existing_date or '-'} "
        f"target={result.backfill.target_date} "
        f"backfill_missing={','.join(item.isoformat() for item in result.backfill.missing_dates) or '-'} "
        f"evaluated={','.join(str(item) for item in result.evaluation.evaluated_forecast_ids) or '-'} "
        f"skipped={','.join(str(item) for item in result.evaluation.skipped_forecast_ids) or '-'}"
    )
    return 1 if result.status == "failed" else 0
