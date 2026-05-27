from pathlib import Path

import httpx
import pytest

from goldfxgraph.cli import main as goldfxgraph_main
from goldfxgraph.market_data.csv_loader import CsvValidationError, load_xauusd_daily_csv
from goldfxgraph.market_data.current_quote import CurrentQuoteProvider, QuoteProviderError
from goldfxgraph.market_data.ingest import import_xauusd_daily_csv_to_db
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import MarketDataRepository
from goldfxgraph.schemas.forecast import DailyBar


def test_load_xauusd_daily_csv_sorts_and_preserves_optional_fields(tmp_path: Path) -> None:
    csv_path = tmp_path / "xauusd.csv"
    csv_path.write_text(
        "Date,Open,High,Low,Close,Volume,Source,Symbol\n"
        "2024-01-02,2050,2060,2040,2055,10,unit,XAUUSD\n"
        "2024-01-01,2040,2050,2030,2045,9,unit,XAUUSD\n",
        encoding="utf-8",
    )

    result = load_xauusd_daily_csv(csv_path)

    assert result.latest_bar.date.isoformat() == "2024-01-02"
    assert result.latest_bar.close == 2055
    assert result.latest_bar.source == "unit"
    assert result.latest_bar.symbol == "XAUUSD"
    assert len(result.bars) == 2


def test_load_repository_csv_fixture() -> None:
    result = load_xauusd_daily_csv(Path("data/raw/xauusd_d.csv"))

    assert result.latest_bar.close > 0
    assert result.bars[0].date <= result.latest_bar.date


def test_load_xauusd_daily_csv_rejects_missing_required_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("Date,Open,High,Close\n2024-01-01,1,2,3\n", encoding="utf-8")

    with pytest.raises(CsvValidationError, match="low"):
        load_xauusd_daily_csv(csv_path)


def test_load_xauusd_daily_csv_rejects_invalid_ohlc_range(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad-range.csv"
    csv_path.write_text("Date,Open,High,Low,Close\n2024-01-01,2050,2040,2030,2055\n", encoding="utf-8")

    with pytest.raises(CsvValidationError, match="within low/high range"):
        load_xauusd_daily_csv(csv_path)


@pytest.mark.asyncio
async def test_import_xauusd_daily_csv_to_db_writes_rows_and_keeps_latest_bar(tmp_path: Path) -> None:
    csv_path = tmp_path / "xauusd.csv"
    csv_path.write_text(
        "date,open,high,low,close,volume,source,symbol\n"
        "2024-01-01,2040,2050,2030,2045,9,unit,XAUUSD\n"
        "2024-01-02,2050,2060,2040,2055,10,unit,XAUUSD\n",
        encoding="utf-8",
    )

    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = MarketDataRepository(session_factory)

    written = await import_xauusd_daily_csv_to_db(csv_path, repository)

    latest = await repository.get_latest_market_bar("XAUUSD")
    count = await repository.get_market_bars_count("XAUUSD")

    assert written == 2
    assert count == 2
    assert latest is not None
    assert latest.date.isoformat() == "2024-01-02"
    assert latest.close == 2055
    assert latest.source == "unit"


@pytest.mark.asyncio
async def test_import_xauusd_daily_csv_to_db_is_idempotent(tmp_path: Path) -> None:
    csv_path = tmp_path / "xauusd.csv"
    csv_path.write_text(
        "date,open,high,low,close,volume,source,symbol\n"
        "2024-01-01,2040,2050,2030,2045,9,unit,XAUUSD\n"
        "2024-01-02,2050,2060,2040,2055,10,unit,XAUUSD\n",
        encoding="utf-8",
    )

    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = MarketDataRepository(session_factory)

    first_written = await import_xauusd_daily_csv_to_db(csv_path, repository)
    second_written = await import_xauusd_daily_csv_to_db(csv_path, repository)
    count = await repository.get_market_bars_count("XAUUSD")

    assert first_written == 2
    assert second_written == 2
    assert count == 2


@pytest.mark.asyncio
async def test_import_xauusd_daily_csv_to_db_rejects_missing_required_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("date,open,high,close\n2024-01-01,1,2,3\n", encoding="utf-8")

    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    repository = MarketDataRepository(session_factory)

    with pytest.raises(CsvValidationError, match="low"):
        await import_xauusd_daily_csv_to_db(csv_path, repository)


def test_daily_bar_rejects_non_finite_or_negative_values() -> None:
    from datetime import date

    with pytest.raises(ValueError):
        DailyBar(date=date(2024, 1, 1), open=-1, high=1, low=1, close=1)

    with pytest.raises(ValueError):
        DailyBar(date=date(2024, 1, 1), open=1, high=float("inf"), low=1, close=1)


def test_current_quote_provider_uses_tradingview_only_and_ignores_legacy_candidates() -> None:
    requested_urls: list[str] = []
    fixture_html = (Path(__file__).parent / "fixtures" / "tradingview_xauusd_page.html").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.host == "www.tradingview.com":
            return httpx.Response(200, text=fixture_html, request=request)
        if request.url.host == "legacy-quote.example.test":
            return httpx.Response(500, request=request)
        return httpx.Response(500, request=request)

    provider = CurrentQuoteProvider(
        url=None,
        api_key="token",
        source_name="legacy-source-name",
        candidate_urls=["https://legacy-quote.example.test/price/XAU"],
        transport=httpx.MockTransport(handler),
    )

    quote = provider.fetch()

    assert requested_urls == ["https://www.tradingview.com/symbols/XAUUSD/"]
    assert quote.symbol == "XAUUSD"
    assert quote.current_price == 4567.78
    assert quote.data_source == "TradingView"
    assert quote.data_timestamp.isoformat() == "2026-05-25T02:09:05.812308+00:00"


def test_tradingview_quote_provider_parses_fixture_html() -> None:
    from goldfxgraph.market_data.tradingview_quote import TradingViewQuoteProvider

    fixture_html = (Path(__file__).parent / "fixtures" / "tradingview_xauusd_page.html").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://www.tradingview.com/symbols/XAUUSD/"
        return httpx.Response(200, text=fixture_html, request=request)

    provider = TradingViewQuoteProvider(transport=httpx.MockTransport(handler))

    quote = provider.fetch()

    assert quote.symbol == "XAUUSD"
    assert quote.current_price == 4567.78
    assert quote.data_source == "TradingView"
    assert quote.data_timestamp.isoformat() == "2026-05-25T02:09:05.812308+00:00"


def test_tradingview_quote_provider_rejects_broken_fixture_html() -> None:
    from goldfxgraph.market_data.tradingview_quote import TradingViewQuoteProvider

    broken_html = (
        Path(__file__).parent / "fixtures" / "tradingview_xauusd_page_broken.html"
    ).read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=broken_html, request=request)

    provider = TradingViewQuoteProvider(transport=httpx.MockTransport(handler))

    with pytest.raises(QuoteProviderError, match="TradingView quote page missing current price"):
        provider.fetch()


def test_tradingview_quote_provider_raises_on_network_failure() -> None:
    from goldfxgraph.market_data.tradingview_quote import TradingViewQuoteProvider

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

    provider = TradingViewQuoteProvider(transport=httpx.MockTransport(handler))

    with pytest.raises(QuoteProviderError, match="TradingView quote request failed"):
        provider.fetch()


def test_current_quote_provider_ignores_non_tradingview_url_override() -> None:
    requested_urls: list[str] = []
    fixture_html = (Path(__file__).parent / "fixtures" / "tradingview_xauusd_page.html").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.host == "www.tradingview.com":
            return httpx.Response(200, text=fixture_html, request=request)
        return httpx.Response(
            500,
            request=request,
        )

    provider = CurrentQuoteProvider(
        url="https://not-tradingview.example.test/latest",
        api_key=None,
        candidate_urls=["https://legacy-quote.example.test/price/XAU"],
        transport=httpx.MockTransport(handler),
    )

    quote = provider.fetch()

    assert requested_urls == ["https://www.tradingview.com/symbols/XAUUSD/"]
    assert quote.symbol == "XAUUSD"
    assert quote.current_price == 4567.78
    assert quote.data_source == "TradingView"


def test_yahoo_history_fetcher_is_removed_from_daily_bar_backfill() -> None:
    from datetime import date

    from goldfxgraph.market_data.yahoo_history import YahooHistoryError, fetch_gold_daily_bars

    with pytest.raises(YahooHistoryError, match="removed; use TradingView history instead"):
        fetch_gold_daily_bars(
            start_date=date(2026, 5, 23),
            end_date=date(2026, 5, 26),
        )


def test_goldfxgraph_cli_dispatches_import_market_data_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = tmp_path / "xauusd.csv"
    captured: dict[str, object] = {}

    def fake_main(argv: list[str] | None = None) -> int:
        captured["argv"] = list(argv or [])
        return 0

    monkeypatch.setattr("goldfxgraph.market_data.ingest.main", fake_main)

    exit_code = goldfxgraph_main(
        [
            "import-market-data",
            "--csv-path",
            str(csv_path),
            "--symbol",
            "XAUUSD",
            "--env-file",
            "dev.env",
        ]
    )

    assert exit_code == 0
    assert captured["argv"] == [
        "--csv-path",
        str(csv_path),
        "--symbol",
        "XAUUSD",
        "--env-file",
        "dev.env",
    ]
