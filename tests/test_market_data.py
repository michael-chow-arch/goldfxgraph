from pathlib import Path

import httpx
import pytest

from goldfxgraph.market_data.csv_loader import CsvValidationError, load_xauusd_daily_csv
from goldfxgraph.market_data.current_quote import CurrentQuoteProvider, QuoteProviderError
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


def test_daily_bar_rejects_non_finite_or_negative_values() -> None:
    from datetime import date

    with pytest.raises(ValueError):
        DailyBar(date=date(2024, 1, 1), open=-1, high=1, low=1, close=1)

    with pytest.raises(ValueError):
        DailyBar(date=date(2024, 1, 1), open=1, high=float("inf"), low=1, close=1)


def test_quote_provider_tries_multiple_sources_until_success() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.host == "first.example.test":
            return httpx.Response(503, request=request)
        if request.url.host == "second.example.test":
            return httpx.Response(
                200,
                json={"close": 2058.5, "data_timestamp": "2024-01-01T00:00:00Z"},
                request=request,
            )
        return httpx.Response(500, request=request)

    provider = CurrentQuoteProvider(
        url="https://first.example.test/latest?apikey=secret",
        api_key="token",
        candidate_urls=[
            "https://second.example.test/quote?apikey=backup-secret",
            "https://third.example.test/quote",
        ],
        transport=httpx.MockTransport(handler),
    )

    quote = provider.fetch()

    assert requested_urls == [
        "https://first.example.test/latest?apikey=secret",
        "https://second.example.test/quote?apikey=backup-secret",
    ]
    assert quote.current_price == 2058.5
    assert quote.data_source == "second.example.test"


def test_quote_provider_returns_controlled_error_when_all_sources_fail() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.host == "first.example.test":
            return httpx.Response(500, request=request)
        return httpx.Response(200, json={"price": "nan", "source": "mock-feed"}, request=request)

    provider = CurrentQuoteProvider(
        url="https://first.example.test/latest?apikey=secret",
        api_key=None,
        candidate_urls=["https://second.example.test/quote?token=secret-backup"],
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(QuoteProviderError, match="Current quote discovery failed"):
        provider.fetch()

    assert requested_urls == [
        "https://first.example.test/latest?apikey=secret",
        "https://second.example.test/quote?token=secret-backup",
    ]


def test_quote_provider_rejects_non_finite_price() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"price": "nan", "source": "unit"}, request=request)

    provider = CurrentQuoteProvider(
        url="https://quote.example.test/latest?apikey=secret",
        api_key=None,
        candidate_urls=[],
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(QuoteProviderError, match="Current quote discovery failed"):
        provider.fetch()


def test_quote_provider_sanitizes_url_fallback_source() -> None:
    captured_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(request.headers)
        return httpx.Response(
            200,
            json={
                "price": 2050.5,
                "timestamp": "2024-01-01T00:00:00Z",
                "source": "https://quote.example.test/latest?apikey=secret",
            },
            request=request,
        )

    provider = CurrentQuoteProvider(
        url="https://quote.example.test/latest?apikey=secret",
        api_key="token",
        candidate_urls=[],
        transport=httpx.MockTransport(handler),
    )

    quote = provider.fetch()

    assert quote.current_price == 2050.5
    assert quote.data_source == "quote.example.test"
    assert "secret" not in quote.data_source
    assert captured_headers["authorization"] == "Bearer token"
