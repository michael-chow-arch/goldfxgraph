from __future__ import annotations

from goldfxgraph.persistence.database import SessionFactory
from goldfxgraph.persistence.external_source_registry import ExternalSourceNotFoundError, ExternalSourceRegistryService

REQUIRED_EXTERNAL_SOURCE_KEYS: tuple[str, ...] = (
    "llm.openai.analysis",
    "tradingview.current_quote",
    "tradingview.history",
    "newsflow.cnbc_markets",
    "newsflow.marketwatch_top_stories",
    "newsflow.google_news_gold",
    "newsflow.google_news_rates",
    "macro.fred.dollar_index",
    "macro.fred.real_rates",
    "macro.cftc.gold_commitments",
    "alt.pizzint.watch",
    "alt.polymarket.zh",
)


class ExternalSourceRegistryValidationError(RuntimeError):
    def __init__(self, missing_source_keys: tuple[str, ...]) -> None:
        self.missing_source_keys = missing_source_keys
        super().__init__("missing required external sources: " + ", ".join(missing_source_keys))


async def validate_required_external_sources(session_factory: SessionFactory) -> int:
    service = ExternalSourceRegistryService(session_factory)
    missing_source_keys: list[str] = []
    for source_key in REQUIRED_EXTERNAL_SOURCE_KEYS:
        try:
            await service.get_active_source(source_key)
        except ExternalSourceNotFoundError:
            missing_source_keys.append(source_key)

    if missing_source_keys:
        raise ExternalSourceRegistryValidationError(tuple(missing_source_keys))
    return len(REQUIRED_EXTERNAL_SOURCE_KEYS)
