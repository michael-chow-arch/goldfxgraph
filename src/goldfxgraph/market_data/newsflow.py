from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree as ET

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DC_NS = "{http://purl.org/dc/elements/1.1/}"

NEWS_SOURCE_LABELS: dict[str, str] = {
    "CNBC Markets": "CNBC 市场",
    "MarketWatch Top Stories": "MarketWatch 头条",
    "Google News Gold": "Google 新闻·黄金",
    "Google News Rates": "Google 新闻·利率",
    "Reuters": "路透社",
    "AD HOC NEWS": "临时新闻",
    "FOREX.com": "外汇平台 FOREX.com",
    "MSN": "MSN 资讯",
}

HEADLINE_PHRASE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        "Gold Markets Frozen in Place as Iran Stalemate and Fed Hawks Battle Central Bank Buying - AD HOC NEWS",
        "黄金市场陷入横盘，伊朗僵局与美联储鹰派、央行买盘拉锯",
    ),
    (
        "U.S. and Iran are closing in on a 60-day ceasefire extension with nuclear framework, FT reports",
        "美国与伊朗正接近将停火延长 60 天，并推进核框架，FT 报道",
    ),
    (
        "This bond strategy can protect your portfolio even if interest rates go up",
        "这类债券策略即使利率上行也能保护组合",
    ),
    (
        "Gold Price Forecast: XAU/USD Clings to Major Support—Breakdown Risk Rises",
        "黄金价格预测：XAU/USD 维持关键支撑，跌破风险上升",
    ),
    (
        "Gold set for weekly loss on stronger dollar, rate-hike bets - MSN",
        "黄金或录得周线下跌，受美元走强和加息押注影响 - MSN 资讯",
    ),
    ("Gold edges higher as Fed cut bets firm", "黄金小幅走高，美联储降息押注继续增强"),
    ("Dollar slips on softer inflation data", "美元因通胀数据偏软而走弱"),
    ("Gold holds near record highs", "黄金徘徊于历史高位附近"),
    ("Gold prices rebound as traders watch rates", "黄金价格反弹，交易员关注利率走势"),
    ("Gold prices rebound", "黄金价格反弹"),
    ("Gold edges higher", "黄金小幅走高"),
    ("Dollar slips", "美元走弱"),
    ("Fed cut bets firm", "市场加大对美联储降息的押注"),
)

HEADLINE_WORD_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("Reuters", "路透社"),
    ("FT", "金融时报"),
    ("Gold", "黄金"),
    ("gold", "黄金"),
    ("Dollar", "美元"),
    ("dollar", "美元"),
    ("Fed", "美联储"),
    ("Inflation", "通胀"),
    ("inflation", "通胀"),
    ("Risk", "风险"),
    ("risk", "风险"),
    ("markets", "市场"),
    ("market", "市场"),
    ("rates", "利率"),
    ("Rate", "利率"),
    ("portfolio", "组合"),
    ("portfolios", "组合"),
    ("hawkish", "鹰派"),
    ("bullion", "金银现货"),
    ("ceasefire extension", "停火延长"),
    ("nuclear framework", "核框架"),
    ("record highs", "历史高位"),
)


@dataclass(frozen=True)
class NewsFeedSource:
    name: str
    url: str


DEFAULT_NEWSFLOW_SOURCES: tuple[NewsFeedSource, ...] = (
    NewsFeedSource(name="CNBC Markets", url="https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    NewsFeedSource(name="MarketWatch Top Stories", url="https://www.marketwatch.com/rss/topstories"),
    NewsFeedSource(
        name="Google News Gold",
        url="https://news.google.com/rss/search?q=gold+market+when:1d&hl=en-US&gl=US&ceid=US:en",
    ),
    NewsFeedSource(
        name="Google News Rates",
        url="https://news.google.com/rss/search?q=Fed+inflation+dollar+gold+when:1d&hl=en-US&gl=US&ceid=US:en",
    ),
)


class NewsflowError(RuntimeError):
    """新闻流源返回无效内容。"""


def fetch_newsflow(
    transport: httpx.BaseTransport | None = None,
    *,
    sources: tuple[NewsFeedSource, ...] = DEFAULT_NEWSFLOW_SOURCES,
    headline_limit: int = 12,
) -> dict[str, Any]:
    feed_statuses: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []

    headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"}
    with httpx.Client(transport=transport, timeout=20, follow_redirects=True, headers=headers) as client:
        for source in sources:
            try:
                response = client.get(source.url)
                response.raise_for_status()
                feed_items = _parse_feed_items(response.text, source.name)
                items.extend(feed_items)
                feed_statuses.append(
                    {
                        "source": source.name,
                        "url": source.url,
                        "status": "available" if feed_items else "empty",
                        "item_count": len(feed_items),
                    }
                )
            except (httpx.HTTPError, NewsflowError) as exc:
                feed_statuses.append(
                    {
                        "source": source.name,
                        "url": source.url,
                        "status": "unavailable",
                        "error": str(exc),
                    }
                )

    headlines = _dedupe_headlines(items)[:headline_limit]
    if not headlines:
        return {
            "status": "unavailable",
            "source": "mainstream-rss",
            "feed_statuses": feed_statuses,
            "headline_count": 0,
            "source_count": 0,
            "headlines": [],
            "top_headlines": [],
            "sentiment": "neutral",
            "sentiment_score": 0,
            "summary": "新闻流暂不可用，当前没有抓取到可验证的主流媒体标题。",
        }

    source_names = _unique_strings([headline["source"] for headline in headlines])
    sentiment_score = _headline_sentiment_score(headlines)
    sentiment = _sentiment_from_score(sentiment_score)
    top_headlines = headlines[:5]
    summary = _build_newsflow_summary(headlines, source_names, sentiment, sentiment_score)

    return {
        "status": "available",
        "source": "mainstream-rss",
        "feed_statuses": feed_statuses,
        "headline_count": len(headlines),
        "source_count": len(source_names),
        "headlines": headlines,
        "top_headlines": top_headlines,
        "sentiment": sentiment,
        "sentiment_score": sentiment_score,
        "summary": summary,
        "topics": _extract_topics(headlines),
    }


def _parse_feed_items(xml_text: str, source_name: str) -> list[dict[str, Any]]:
    text = xml_text.strip()
    if not text:
        raise NewsflowError("news feed body is empty")

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise NewsflowError("news feed is not valid XML") from exc

    items = _parse_rss_items(root, source_name)
    if items:
        return items
    items = _parse_atom_items(root, source_name)
    if items:
        return items
    raise NewsflowError("news feed does not contain RSS or Atom items")


def _parse_rss_items(root: ET.Element, source_name: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        title = _clean_text(item.findtext("title"))
        if not title:
            continue
        link = _clean_text(item.findtext("link"))
        published_at = _parse_timestamp(item.findtext("pubDate") or item.findtext(f"{DC_NS}date"))
        item_source = _clean_text(item.findtext("source")) or source_name
        items.append(
            {
                "title": title,
                "title_cn": translate_headline_to_chinese(title),
                "link": link,
                "source": item_source,
                "source_cn": translate_source_name_to_chinese(item_source),
                "published_at": published_at.isoformat() if published_at else None,
            }
        )
    return items


def _parse_atom_items(root: ET.Element, source_name: str) -> list[dict[str, Any]]:
    atom_ns = "{http://www.w3.org/2005/Atom}"
    items: list[dict[str, Any]] = []
    for entry in root.findall(f".//{atom_ns}entry"):
        title = _clean_text(entry.findtext(f"{atom_ns}title"))
        if not title:
            continue
        link = _extract_atom_link(entry, atom_ns)
        published_at = _parse_timestamp(
            entry.findtext(f"{atom_ns}published") or entry.findtext(f"{atom_ns}updated")
        )
        item_source = _clean_text(entry.findtext(f"{atom_ns}source/{atom_ns}title")) or source_name
        items.append(
            {
                "title": title,
                "title_cn": translate_headline_to_chinese(title),
                "link": link,
                "source": item_source,
                "source_cn": translate_source_name_to_chinese(item_source),
                "published_at": published_at.isoformat() if published_at else None,
            }
        )
    return items


def _extract_atom_link(entry: ET.Element, atom_ns: str) -> str | None:
    for link in entry.findall(f"{atom_ns}link"):
        href = link.attrib.get("href")
        if href:
            return href
        if link.text and link.text.strip():
            return link.text.strip()
    return None


def _dedupe_headlines(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in sorted(items, key=_headline_sort_key, reverse=True):
        key = (item["title"], item.get("source") or "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _headline_sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("published_at") or ""), str(item.get("title") or ""))


def _build_newsflow_summary(
    headlines: list[dict[str, Any]],
    source_names: list[str],
    sentiment: str,
    sentiment_score: int,
) -> str:
    representative_lines = []
    for headline in headlines[:3]:
        source = translate_source_name_to_chinese(str(headline.get("source") or ""))
        title_cn = str(headline.get("title_cn") or headline.get("title") or "").strip()
        if title_cn:
            representative_lines.append(f"{source}：{title_cn}")
    tone_map = {
        "bullish": "看多",
        "bearish": "看空",
        "neutral": "中性",
    }
    lines = [
        f"新闻流已从 {len(source_names)} 个主流媒体源抓取到 {len(headlines)} 条标题。",
        "整体情绪为"
        f"{tone_map.get(sentiment, '中性')}（评分 {sentiment_score:+d}），主题聚焦 "
        f"{'、'.join(_translate_topic(topic) for topic in _extract_topics(headlines)) or '暂无明显主题'}。",
    ]
    if representative_lines:
        lines.append("代表性标题：")
        lines.extend(f"- {line}" for line in representative_lines)
    return "\n".join(lines)


def _headline_sentiment_score(headlines: list[dict[str, Any]]) -> int:
    bullish_terms = {
        "higher",
        "rally",
        "rebound",
        "record",
        "cuts",
        "slips",
        "weaker",
        "easing",
        "gains",
        "safe haven",
        "gold higher",
        "gold holds",
    }
    bearish_terms = {
        "fall",
        "falls",
        "drop",
        "drops",
        "hawkish",
        "strong dollar",
        "higher rates",
        "inflation",
        "selloff",
        "retreat",
        "pressure",
    }

    score = 0
    for headline in headlines:
        title = str(headline.get("title") or "").lower()
        for term in bullish_terms:
            if term in title:
                score += 1
        for term in bearish_terms:
            if term in title:
                score -= 1
    return score


def _sentiment_from_score(score: int) -> str:
    if score >= 2:
        return "bullish"
    if score <= -2:
        return "bearish"
    return "neutral"


def _extract_topics(headlines: list[dict[str, Any]]) -> list[str]:
    keywords = {
        "Fed": ["fed", "rates", "cut", "hawkish"],
        "Dollar": ["dollar", "usd"],
        "Inflation": ["inflation", "cpi", "ppi"],
        "Gold": ["gold", "xau", "bullion"],
        "Risk": ["war", "tariff", "geopolitical", "recession"],
    }
    topics: list[str] = []
    joined_titles = " ".join(str(headline.get("title") or "").lower() for headline in headlines)
    for topic, terms in keywords.items():
        if any(term in joined_titles for term in terms):
            topics.append(topic)
    return topics


def _translate_topic(topic: str) -> str:
    return {
        "Fed": "美联储",
        "Dollar": "美元",
        "Inflation": "通胀",
        "Gold": "黄金",
        "Risk": "风险",
    }.get(topic, topic)


def translate_source_name_to_chinese(source_name: str) -> str:
    rendered = source_name.strip()
    if not rendered:
        return "未知来源"
    return NEWS_SOURCE_LABELS.get(rendered, rendered)


def translate_headline_to_chinese(title: str) -> str:
    rendered = title
    for english, chinese in HEADLINE_PHRASE_REPLACEMENTS:
        rendered = rendered.replace(english, chinese)
    for english, chinese in HEADLINE_WORD_REPLACEMENTS:
        rendered = rendered.replace(english, chinese)
    rendered = rendered.replace("  ", " ")
    rendered = rendered.strip(" :-")
    return rendered


def _parse_timestamp(value: str | None) -> datetime | None:
    rendered = _clean_text(value)
    if not rendered:
        return None
    try:
        parsed = parsedate_to_datetime(rendered)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(rendered.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _clean_text(value: str | None) -> str:
    return (value or "").strip()


def _unique_strings(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique
