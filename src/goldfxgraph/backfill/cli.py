from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from goldfxgraph.backfill.eod_backfill import BackfillValidationError, run_eod_backfill
from goldfxgraph.packages.common.settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goldfxgraph backfill")
    parser.add_argument("--csv-path", type=Path, default=None, help="Override the XAUUSD CSV path")
    parser.add_argument("--as-of", dest="as_of", default=None, help="Optional ISO timestamp for deterministic runs")
    parser.add_argument("--env-file", type=Path, default=Path("dev.env"), help="Optional settings env file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = load_settings(env_file=args.env_file)

    now = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    try:
        result = run_eod_backfill(settings=settings, now=now, csv_path=args.csv_path)
    except BackfillValidationError as exc:
        print(f"backfill failed: {exc}", file=sys.stderr)
        return 1

    status = "written" if result.written else "no-op"
    missing = ",".join(date.isoformat() for date in result.missing_dates) or "-"
    target_date = getattr(result, "target_date", None)
    print(f"backfill {status}: latest={result.latest_existing_date} target={target_date} missing={missing}")
    return 0
