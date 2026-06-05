from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from goldfxgraph.persistence.external_source_registry import ExternalSourceSnapshot

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

GOLD_RELEVANCE_TERMS = (
    "gold",
    "xau",
    "bullion",
    "gold price",
    "gold prices",
    "gold market",
    "fed",
    "interest rate",
    "rates",
    "inflation",
    "cpi",
    "ppi",
    "dollar",
    "usd",
    "real yield",
    "yield",
    "geopolitical",
    "war",
    "tariff",
    "recession",
    "risk",
    "central bank",
)

POLYMARKET_TITLE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("Will gold price rise above", "黄金价格是否会升破"),
    ("Will the Fed cut rates in June?", "美联储6月是否降息？"),
    ("Will the Fed cut rates in June", "美联储6月是否降息"),
    ("Will the Fed cut rates", "美联储是否降息"),
    ("Will", "是否会"),
    ("rise above", "升破"),
    ("fall below", "跌破"),
    ("cut rates", "降息"),
    ("by June", "在6月前"),
    ("in June", "在6月"),
    ("higher for longer", "利率更久维持高位"),
    ("stronger dollar", "美元走强"),
    ("softer inflation data", "偏弱通胀数据"),
    ("traders watch rates", "交易员关注利率"),
    ("holds near record highs", "维持在历史高位附近"),
    ("rebounds as traders watch rates", "在交易员关注利率时反弹"),
    ("Gold", "黄金"),
    ("gold", "黄金"),
    ("XAU", "XAU"),
    ("Fed", "美联储"),
    ("fed", "美联储"),
    ("Interest Rate", "利率"),
    ("interest rate", "利率"),
    ("Rates", "利率"),
    ("rates", "利率"),
    ("Inflation", "通胀"),
    ("inflation", "通胀"),
    ("Dollar", "美元"),
    ("dollar", "美元"),
    ("USD", "美元"),
    ("usd", "美元"),
    ("CPI", "CPI"),
    ("PPI", "PPI"),
    ("War", "战争"),
    ("war", "战争"),
    ("Tariff", "关税"),
    ("tariff", "关税"),
    ("Recession", "衰退"),
    ("recession", "衰退"),
    ("Geopolitical", "地缘政治"),
    ("geopolitical", "地缘政治"),
    ("Yield", "收益率"),
    ("yield", "收益率"),
    ("June", "6月"),
    ("june", "6月"),
    ("Central Bank", "央行"),
    ("central bank", "央行"),
)


class PolymarketError(RuntimeError):
    """Polymarket 公共页面不可用或无法解析。"""


@dataclass(frozen=True)
class PolymarketMarket:
    title: str
    title_cn: str
    url: str | None
    probability: float | None
    liquidity: float | None
    volume: float | None
    close_time: datetime | None
    relevance_score: int
    relevance_label: str
    signal_bias: str
    signal_reason: str


def fetch_polymarket_inputs(
    source: ExternalSourceSnapshot,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    with httpx.Client(transport=transport, timeout=20, follow_redirects=True, headers=headers) as client:
        response = client.get(source.endpoint_url)
        response.raise_for_status()

    html_text = response.text
    raw_candidates = _extract_market_candidates(html_text, base_url=source.endpoint_url)
    markets = [_normalize_market(candidate, base_url=source.endpoint_url) for candidate in raw_candidates]
    markets = [market for market in markets if market.relevance_score > 0]
    markets.sort(key=lambda item: (item.relevance_score, item.probability or 0.0, item.liquidity or 0.0), reverse=True)

    if not markets:
        raise PolymarketError("polymarket page did not expose any gold-related public markets")

    bullish_count = sum(1 for market in markets if market.signal_bias == "bullish")
    bearish_count = sum(1 for market in markets if market.signal_bias == "bearish")
    neutral_count = len(markets) - bullish_count - bearish_count

    summary = _build_summary(markets, bullish_count, bearish_count, neutral_count)
    market_payloads = [
        {
            "title": market.title,
            "title_cn": market.title_cn,
            "url": market.url,
            "probability": market.probability,
            "liquidity": market.liquidity,
            "volume": market.volume,
            "close_time": market.close_time.isoformat() if market.close_time else None,
            "relevance_score": market.relevance_score,
            "relevance_label": market.relevance_label,
            "signal_bias": market.signal_bias,
            "signal_reason": market.signal_reason,
        }
        for market in markets[:8]
    ]

    return {
        "status": "available",
        "source": _source_name(source),
        "url": source.endpoint_url,
        "market_count": len(raw_candidates),
        "gold_related_market_count": len(markets),
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "neutral_count": neutral_count,
        "markets": market_payloads,
        "summary": summary,
    }


def _extract_market_candidates(html_text: str, *, base_url: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for blob in _extract_json_blobs(html_text):
        candidates.extend(_walk_for_markets(blob, base_url=base_url))
    if candidates:
        return candidates

    for href, text in _extract_anchor_candidates(html_text):
        if not text:
            continue
        candidates.append(
            {
                "title": text,
                "url": href,
            }
        )
    return candidates


def _extract_json_blobs(html_text: str) -> list[Any]:
    blobs: list[Any] = []
    for match in re.finditer(
        r"<script[^>]*(?:id=['\"]__NEXT_DATA__['\"][^>]*)?type=['\"]application/json['\"][^>]*>(.*?)</script>",
        html_text,
        re.S | re.I,
    ):
        content = html_lib.unescape(match.group(1)).strip()
        if not content:
            continue
        try:
            blobs.append(json.loads(content))
        except json.JSONDecodeError:
            continue

    if blobs:
        return blobs

    for match in re.finditer(r"<script[^>]*id=['\"]__NEXT_DATA__['\"][^>]*>(.*?)</script>", html_text, re.S | re.I):
        content = html_lib.unescape(match.group(1)).strip()
        if not content:
            continue
        try:
            blobs.append(json.loads(content))
        except json.JSONDecodeError:
            continue

    return blobs


def _walk_for_markets(node: Any, *, base_url: str) -> list[dict[str, Any]]:
    markets: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if _looks_like_market(node):
            markets.append(dict(node))
        for value in node.values():
            markets.extend(_walk_for_markets(value, base_url=base_url))
    elif isinstance(node, list):
        for item in node:
            markets.extend(_walk_for_markets(item, base_url=base_url))
    return markets


def _looks_like_market(node: dict[str, Any]) -> bool:
    title = str(node.get("question") or node.get("title") or node.get("name") or node.get("subtitle") or "").strip()
    if not title:
        return False
    return any(
        key in node
        for key in (
            "probability",
            "yesPrice",
            "liquidity",
            "volume",
            "slug",
            "endDate",
            "closeTime",
            "endsAt",
        )
    )


def _extract_anchor_candidates(html_text: str) -> list[tuple[str | None, str]]:
    candidates: list[tuple[str | None, str]] = []
    pattern = re.compile(r"<a[^>]+href=['\"](?P<href>[^'\"]+)['\"][^>]*>(?P<body>.*?)</a>", re.S | re.I)
    for match in pattern.finditer(html_text):
        href = html_lib.unescape(match.group("href").strip())
        body = html_lib.unescape(re.sub(r"<[^>]+>", " ", match.group("body")))
        text = _clean_text(body)
        if not text:
            continue
        candidates.append((href, text))
    return candidates


def _normalize_market(candidate: dict[str, Any], *, base_url: str) -> PolymarketMarket:
    title = _clean_text(
        str(
            candidate.get("question")
            or candidate.get("title")
            or candidate.get("name")
            or candidate.get("subtitle")
            or ""
        )
    )
    description = _clean_text(str(candidate.get("description") or candidate.get("body") or ""))
    slug = _clean_text(str(candidate.get("slug") or ""))
    url = _candidate_url(candidate, base_url=base_url, slug=slug)
    probability = _normalize_probability(
        candidate.get("probability")
        or candidate.get("yesPrice")
        or candidate.get("price")
        or candidate.get("bestAsk")
        or candidate.get("bestBid")
    )
    liquidity = _normalize_number(candidate.get("liquidity") or candidate.get("liquidityValue"))
    volume = _normalize_number(candidate.get("volume") or candidate.get("tradingVolume"))
    close_time = _parse_datetime(candidate.get("endDate") or candidate.get("closeTime") or candidate.get("endsAt"))
    title_cn = translate_polymarket_title_to_chinese(title)
    relevance_score, relevance_label = _relevance_score(title, description, slug)
    signal_bias, signal_reason = _signal_bias(title, description)
    return PolymarketMarket(
        title=title,
        title_cn=title_cn,
        url=url,
        probability=probability,
        liquidity=liquidity,
        volume=volume,
        close_time=close_time,
        relevance_score=relevance_score,
        relevance_label=relevance_label,
        signal_bias=signal_bias,
        signal_reason=signal_reason,
    )


def _candidate_url(candidate: dict[str, Any], *, base_url: str, slug: str) -> str | None:
    raw_url = _clean_text(str(candidate.get("url") or candidate.get("href") or ""))
    if raw_url:
        if raw_url.startswith("http"):
            return raw_url
        return urljoin(base_url, raw_url)
    if slug:
        return urljoin(base_url, f"/market/{slug}")
    return None


def _relevance_score(title: str, description: str, slug: str) -> tuple[int, str]:
    haystack = f"{title} {description} {slug}".lower()
    score = 0
    for term in GOLD_RELEVANCE_TERMS:
        if term in haystack:
            score += 1
    if score >= 5:
        return score, "high"
    if score >= 2:
        return score, "medium"
    return score, "low"


def _signal_bias(title: str, description: str) -> tuple[str, str]:
    haystack = f"{title} {description}".lower()
    bullish_terms = (
        "gold",
        "rate cut",
        "cuts",
        "inflation",
        "recession",
        "war",
        "tariff",
        "risk",
        "dovish",
        "weak dollar",
        "dollar down",
        "lower rates",
    )
    bearish_terms = (
        "higher for longer",
        "rate hike",
        "hawkish",
        "strong dollar",
        "dollar up",
        "yields up",
        "real yields",
        "tightening",
        "inflation cools",
    )
    if any(term in haystack for term in bullish_terms):
        return "bullish", "市场定价对黄金更友好的事件概率在抬升"
    if any(term in haystack for term in bearish_terms):
        return "bearish", "市场定价对黄金不友好的事件概率在抬升"
    return "neutral", "当前标题更偏宏观背景，暂未形成明确单边倾向"


def _normalize_probability(value: Any) -> float | None:
    if value is None:
        return None
    rendered = str(value).strip().replace("%", "")
    if not rendered:
        return None
    try:
        parsed = float(rendered)
    except ValueError:
        return None
    if parsed > 1 and parsed <= 100:
        parsed /= 100
    if parsed < 0:
        return None
    return round(min(parsed, 1.0), 4)


def _normalize_number(value: Any) -> float | None:
    if value is None:
        return None
    rendered = str(value).strip().replace(",", "")
    if not rendered:
        return None
    try:
        parsed = float(rendered)
    except ValueError:
        return None
    if not parsed == parsed:
        return None
    return parsed


def _parse_datetime(value: Any) -> datetime | None:
    rendered = str(value or "").strip()
    if not rendered:
        return None
    if rendered.endswith("Z"):
        rendered = f"{rendered[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(rendered)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _build_summary(
    markets: list[PolymarketMarket],
    bullish_count: int,
    bearish_count: int,
    neutral_count: int,
) -> str:
    top_markets = markets[:3]
    lines = [
        f"Polymarket 公开页已抓取到 {len(markets)} 个与黄金相关的候选市场。"
        f"其中偏多 {bullish_count} 个，偏空 {bearish_count} 个，中性 {neutral_count} 个。",
    ]
    if top_markets:
        lines.append("代表性市场：")
        for market in top_markets:
            probability_text = f"{market.probability * 100:.0f}%" if market.probability is not None else "未知概率"
            liquidity_text = f"{market.liquidity:.0f}" if market.liquidity is not None else "未知流动性"
            lines.append(
                f"- {market.title_cn}（概率 {probability_text}，流动性 {liquidity_text}，"
                f"相关度 {market.relevance_label}，{market.signal_reason}）"
            )
    return "\n".join(lines)


def translate_polymarket_title_to_chinese(title: str) -> str:
    rendered = title
    for english, chinese in POLYMARKET_TITLE_REPLACEMENTS:
        rendered = rendered.replace(english, chinese)
    rendered = rendered.replace("  ", " ")
    return _clean_text(rendered)


def _clean_text(value: str | None) -> str:
    return html_lib.unescape((value or "").strip())


def _source_name(source: ExternalSourceSnapshot) -> str:
    value = source.request_config.get("source_name")
    rendered = str(value or "").strip()
    return rendered or source.source_key
