from __future__ import annotations

import sys

from goldfxgraph.backfill.cli import main as backfill_main


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Usage: goldfxgraph backfill [options]")
        return 0

    command, *rest = args
    if command == "backfill":
        return backfill_main(rest)

    print(f"Unknown command: {command}")
    print("Usage: goldfxgraph backfill [options]")
    return 1
