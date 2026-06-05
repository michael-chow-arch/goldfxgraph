from __future__ import annotations

from datetime import UTC, datetime

import httpx

from goldfxgraph.persistence.external_source_registry import ExternalSourceSnapshot
from goldfxgraph.market_data.pizza_index import fetch_pizza_index

TEST_PIZZA_BASE_URL = "https://example.test/pizzint"


def test_fetch_pizza_index_parses_public_dashboard_snapshot() -> None:
    html = (
        "<!doctype html><html><body>"
        "<div class='text-4xl sm:text-5xl lg:text-6xl font-bold text-yellow-400 leading-none -mb-1'>"
        "DOUGHCON 3</div>"
        "<div class='text-xs sm:text-sm text-yellow-400 opacity-80 leading-tight flex flex-wrap items-center gap-1'>"
        "<span>ROUND HOUSE</span><span class='opacity-60'>•</span>"
        "<span>INCREASE IN FORCE READINESS</span></div>"
        "<div data-place-id='ChIJI6ACK7q2t4kRFcPtFhUuYhU'>"
        "<h3>DOMINO&#x27;S PIZZA</h3>"
        "<span class='text-red-300 font-bold'>178<!-- -->% SPIKE</span>"
        "<div class='text-xs text-gray-400 font-mono'>1.4 mi</div></div>"
        "<div data-place-id='ChIJcYireCe3t4kR4d9trEbGYjc'>"
        "<h3>EXTREME PIZZA</h3>"
        "<span class='text-red-300 font-bold'>270<!-- -->% SPIKE</span>"
        "<div class='text-xs text-gray-400 font-mono'>1.0 mi</div></div>"
        "</body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "example.test"
        return httpx.Response(200, text=html, request=request)

    source = ExternalSourceSnapshot(
        id=1,
        source_key="alt.pizzint.watch",
        source_type="html",
        endpoint_url=f"{TEST_PIZZA_BASE_URL}/watch/",
        request_config={"source_name": "Pizzint Watch"},
        version="1.0.0",
        is_active=True,
        description="测试外部源",
        change_notes="测试数据",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    result = fetch_pizza_index(source, httpx.MockTransport(handler))

    assert result["status"] == "available"
    assert result["doughcon_level"] == 3
    assert result["source_count"] == 2
    assert result["top_locations"][0]["name"] == "EXTREME PIZZA"
    assert result["top_locations"][0]["spike_pct"] == 270
    assert result["top_locations"][1]["name"] == "DOMINO'S PIZZA"
    assert result["pizza_index_score"] > 0
    assert "DOUGHCON 3" in result["summary"]
