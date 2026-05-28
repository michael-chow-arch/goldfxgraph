from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from goldfxgraph.market_data.csv_loader import CsvValidationError, load_xauusd_daily_csv
from goldfxgraph.packages.common.settings import GoldFXGraphSettings, load_settings
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import MarketDataRepository
from goldfxgraph.schemas.forecast import MarketDataSet


def build_market_data_set_from_csv(csv_path: Path, *, symbol: str | None = None) -> MarketDataSet:
    market_data = load_xauusd_daily_csv(csv_path)
    return validate_market_data_ready(market_data, symbol=symbol)


def validate_market_data_ready(market_data: MarketDataSet, *, symbol: str | None = None) -> MarketDataSet:
    if not market_data.bars:
        raise CsvValidationError("CSV import requires at least one completed daily bar")

    latest_bar = market_data.latest_bar
    if latest_bar != market_data.bars[-1]:
        raise CsvValidationError("CSV bars must be sorted in ascending date order")

    normalized_symbol = _normalize_symbol(symbol)
    bar_symbols = {_normalize_symbol(bar.symbol) for bar in market_data.bars}
    if len(bar_symbols) != 1:
        raise CsvValidationError("CSV rows must use a single consistent symbol")

    dataset_symbol = _normalize_symbol(market_data.symbol)
    if normalized_symbol is not None and dataset_symbol != normalized_symbol:
        raise CsvValidationError(f"CSV symbol {dataset_symbol} does not match requested symbol {normalized_symbol}")

    return market_data


async def import_xauusd_daily_csv_to_db(csv_path: Path, repository: MarketDataRepository) -> int:
    market_data = build_market_data_set_from_csv(csv_path)
    validate_market_data_ready(market_data)
    return await repository.upsert_market_bars(market_data.bars)


def build_import_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goldfxgraph import-market-data")
    parser.add_argument("--csv-path", type=Path, default=None, help="Override the XAUUSD CSV path")
    parser.add_argument("--env-file", type=Path, default=Path("dev.env"), help="Optional settings env file")
    parser.add_argument("--symbol", default="XAUUSD", help="Expected market data symbol")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_import_parser()
    args = parser.parse_args(argv)

    settings = load_settings(env_file=args.env_file)
    csv_path = args.csv_path or settings.xauusd_csv_path
    symbol = _normalize_symbol(args.symbol) or "XAUUSD"

    try:
        result = asyncio.run(_run_import(settings=settings, csv_path=csv_path, symbol=symbol))
    except CsvValidationError as exc:
        print(f"import-market-data failed: {exc}", file=sys.stderr)
        return 1

    return result


async def _run_import(*, settings: GoldFXGraphSettings, csv_path: Path, symbol: str) -> int:
    session_factory = create_session_factory(str(settings.database_url))
    try:
        await init_models(session_factory.engine)
        repository = MarketDataRepository(session_factory)
        market_data = build_market_data_set_from_csv(csv_path, symbol=symbol)
        written = await repository.upsert_market_bars(market_data.bars)
        latest = await repository.get_latest_market_bar(symbol)
    except Exception as exc:  # noqa: BLE001
        print(f"import-market-data failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await session_factory.engine.dispose()

    latest_date = latest.date.isoformat() if latest is not None else market_data.latest_bar.date.isoformat()
    print(f"import-market-data written={written} latest={latest_date} symbol={symbol}")
    return 0


def _normalize_symbol(symbol: str | None) -> str | None:
    if symbol is None:
        return None
    rendered = symbol.strip().upper()
    return rendered or None
