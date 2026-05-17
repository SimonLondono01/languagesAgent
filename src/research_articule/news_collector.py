"""Collect news from a secure RSS/Atom source."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from pathlib import Path
import re
import ssl
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


DEFAULT_NEWS_SOURCE = "https://feeds.bbci.co.uk/news/rss.xml"
REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "languagesAgent-news-collector/1.0"


@dataclass(frozen=True)
class NewsItem:
    """Normalized news item parsed from RSS or Atom."""

    title: str
    link: str
    summary: str = ""
    published: str = ""


def collect_news(
    source_url: str = DEFAULT_NEWS_SOURCE,
    max_items: int = 5,
    output_file: str | Path | None = None,
) -> str:
    """Collect news from a secure source and return it as a formatted string.

    The source must use HTTPS. RSS and Atom feeds are supported, and TLS
    certificates are verified through Python's default SSL context.

    Args:
        source_url: HTTPS RSS or Atom feed URL.
        max_items: Maximum number of news entries to include.
        output_file: Optional path where the collected news is saved as a
            UTF-8 text file.

    Returns:
        A human-readable string containing the collected news entries.

    Raises:
        ValueError: If the URL is not HTTPS or max_items is invalid.
        RuntimeError: If the source cannot be fetched or parsed.
    """

    if max_items < 1:
        raise ValueError("max_items must be at least 1")

    _validate_secure_url(source_url)
    feed_content = _fetch_secure_feed(source_url)
    news_items = list(_parse_feed(feed_content))[:max_items]

    if not news_items:
        news_text = "No news items were found."
    else:
        news_text = _format_news(news_items)

    if output_file is not None:
        _save_news_text(news_text, output_file)

    return news_text


def _validate_secure_url(source_url: str) -> None:
    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ValueError("source_url must be a valid HTTPS URL")


def _fetch_secure_feed(source_url: str) -> bytes:
    request = Request(source_url, headers={"User-Agent": USER_AGENT})
    ssl_context = ssl.create_default_context()

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS, context=ssl_context) as response:
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"News source returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Unable to reach news source: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Timed out while contacting news source") from exc


def _parse_feed(feed_content: bytes) -> Iterable[NewsItem]:
    try:
        root = ET.fromstring(feed_content)
    except ET.ParseError as exc:
        raise RuntimeError("News source did not return valid RSS or Atom XML") from exc

    if root.tag.endswith("rss") or root.find("channel") is not None:
        return _parse_rss(root)

    if root.tag.endswith("feed"):
        return _parse_atom(root)

    raise RuntimeError("Unsupported news feed format")


def _parse_rss(root: ET.Element) -> Iterable[NewsItem]:
    channel = root.find("channel")
    if channel is None:
        return []

    items = []
    for item in channel.findall("item"):
        items.append(
            NewsItem(
                title=_clean_text(_find_text(item, "title")),
                link=_clean_text(_find_text(item, "link")),
                summary=_clean_text(_find_text(item, "description")),
                published=_clean_text(_find_text(item, "pubDate")),
            )
        )
    return items


def _parse_atom(root: ET.Element) -> Iterable[NewsItem]:
    namespace = _namespace(root.tag)
    entry_tag = f"{{{namespace}}}entry" if namespace else "entry"
    title_tag = f"{{{namespace}}}title" if namespace else "title"
    summary_tag = f"{{{namespace}}}summary" if namespace else "summary"
    updated_tag = f"{{{namespace}}}updated" if namespace else "updated"
    link_tag = f"{{{namespace}}}link" if namespace else "link"

    items = []
    for entry in root.findall(entry_tag):
        link = ""
        link_node = entry.find(link_tag)
        if link_node is not None:
            link = link_node.attrib.get("href", link_node.text or "")

        items.append(
            NewsItem(
                title=_clean_text(_find_text(entry, title_tag)),
                link=_clean_text(link),
                summary=_clean_text(_find_text(entry, summary_tag)),
                published=_clean_text(_find_text(entry, updated_tag)),
            )
        )
    return items


def _namespace(tag: str) -> str:
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return ""


def _find_text(element: ET.Element, tag: str) -> str:
    node = element.find(tag)
    if node is None or node.text is None:
        return ""
    return node.text


def _clean_text(value: str) -> str:
    text = unescape(value or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _format_news(news_items: Iterable[NewsItem]) -> str:
    lines = ["Collected news:"]
    for index, item in enumerate(news_items, start=1):
        lines.append(f"{index}. {item.title or 'Untitled'}")
        if item.published:
            lines.append(f"   Published: {item.published}")
        if item.summary:
            lines.append(f"   Summary: {item.summary}")
        if item.link:
            lines.append(f"   Link: {item.link}")
    return "\n".join(lines)


def _save_news_text(news_text: str, output_file: str | Path) -> None:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(news_text, encoding="utf-8")
