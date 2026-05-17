"""Collect paragraph text from news articles linked by a secure feed."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Iterable

from .news_collector import (
    DEFAULT_NEWS_SOURCE,
    _fetch_secure_feed,
    _parse_feed,
    _save_news_text,
    _validate_secure_url,
)


class ParagraphHTMLParser(HTMLParser):
    """Extract readable paragraph text from an HTML page."""

    def __init__(self) -> None:
        super().__init__()
        self._inside_paragraph = False
        self._current_parts: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self._inside_paragraph = True
            self._current_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag != "p" or not self._inside_paragraph:
            return

        paragraph = _clean_paragraph(" ".join(self._current_parts))
        if paragraph:
            self.paragraphs.append(paragraph)

        self._inside_paragraph = False
        self._current_parts = []

    def handle_data(self, data: str) -> None:
        if self._inside_paragraph:
            self._current_parts.append(data)


def collect_article_paragraphs(
    source_url: str = DEFAULT_NEWS_SOURCE,
    max_items: int = 3,
    max_paragraphs_per_article: int = 4,
    output_file: str | Path | None = None,
) -> str:
    """Collect paragraphs from news articles linked by a secure RSS/Atom feed.

    Args:
        source_url: HTTPS RSS or Atom feed URL.
        max_items: Maximum number of article links to follow.
        max_paragraphs_per_article: Maximum paragraphs to include per article.
        output_file: Optional path where the collected paragraphs are saved as
            a UTF-8 text file.

    Returns:
        A human-readable string with article titles, links, and paragraphs.

    Raises:
        ValueError: If numeric limits are invalid or a URL is not HTTPS.
        RuntimeError: If the feed or article pages cannot be fetched or parsed.
    """

    if max_items < 1:
        raise ValueError("max_items must be at least 1")
    if max_paragraphs_per_article < 1:
        raise ValueError("max_paragraphs_per_article must be at least 1")

    _validate_secure_url(source_url)
    feed_content = _fetch_secure_feed(source_url)
    news_items = list(_parse_feed(feed_content))[:max_items]

    if not news_items:
        article_text = "No news items were found."
    else:
        article_text = _format_articles(news_items, max_paragraphs_per_article)

    if output_file is not None:
        _save_news_text(article_text, output_file)

    return article_text


def _format_articles(news_items: Iterable[object], max_paragraphs_per_article: int) -> str:
    lines = ["Collected article paragraphs:"]

    for index, item in enumerate(news_items, start=1):
        title = getattr(item, "title", "") or "Untitled"
        link = getattr(item, "link", "")

        lines.append(f"{index}. {title}")
        if link:
            lines.append(f"   Link: {link}")

        paragraphs = _extract_article_paragraphs(link, max_paragraphs_per_article) if link else []
        if paragraphs:
            for paragraph_index, paragraph in enumerate(paragraphs, start=1):
                lines.append(f"   Paragraph {paragraph_index}: {paragraph}")
        else:
            lines.append("   Paragraphs: No paragraphs found.")

    return "\n".join(lines)


def _extract_article_paragraphs(article_url: str, max_paragraphs: int) -> list[str]:
    _validate_secure_url(article_url)
    article_html = _fetch_secure_feed(article_url)
    return _parse_article_paragraphs(article_html)[:max_paragraphs]


def _parse_article_paragraphs(article_html: bytes) -> list[str]:
    parser = ParagraphHTMLParser()
    parser.feed(article_html.decode("utf-8", errors="ignore"))
    parser.close()
    return parser.paragraphs


def _clean_paragraph(value: str) -> str:
    text = re.sub(r"\s+", " ", value)
    return text.strip()
