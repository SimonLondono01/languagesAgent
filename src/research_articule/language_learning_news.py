"""Collect longer news texts for language-learning exercises."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from .article_paragraph_collector import _extract_article_paragraphs
from .news_collector import (
    NewsItem,
    _fetch_secure_feed,
    _parse_feed,
    _save_news_text,
    _validate_secure_url,
)


BBC_FRENCH_NEWS_SOURCE = "https://bbc.github.io/world-service-rss/afrique.html"
SKIPPED_PARAGRAPH_PREFIXES = (
    "crédit photo",
    "source de l'image",
    "légende image",
    "image caption",
)


class BBCWorldServiceHTMLParser(HTMLParser):
    """Parse BBC World Service language listing pages."""

    def __init__(self) -> None:
        super().__init__()
        self.items: list[NewsItem] = []
        self._current_item: dict[str, str] | None = None
        self._inside_heading_link = False
        self._inside_paragraph = False
        self._paragraphs_after_heading = 0
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)

        if tag == "h2":
            self._finish_current_item()
            self._current_item = {"title": "", "link": "", "published": "", "summary": ""}
            self._paragraphs_after_heading = 0

        if tag == "a" and self._current_item is not None and not self._current_item["title"]:
            self._inside_heading_link = True
            self._current_item["link"] = attrs_map.get("href") or ""
            self._text_parts = []

        if tag == "p" and self._current_item is not None:
            self._inside_paragraph = True
            self._text_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._inside_heading_link:
            if self._current_item is not None:
                self._current_item["title"] = " ".join(self._text_parts).strip()
            self._inside_heading_link = False
            self._text_parts = []

        if tag == "p" and self._inside_paragraph:
            paragraph_text = " ".join(self._text_parts).strip()
            if self._current_item is not None and paragraph_text:
                self._paragraphs_after_heading += 1
                if self._paragraphs_after_heading == 1:
                    self._current_item["published"] = paragraph_text
                elif self._paragraphs_after_heading == 2:
                    self._current_item["summary"] = paragraph_text

            self._inside_paragraph = False
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._inside_heading_link or self._inside_paragraph:
            text = data.strip()
            if text:
                self._text_parts.append(text)

    def close(self) -> None:
        super().close()
        self._finish_current_item()

    def _finish_current_item(self) -> None:
        if not self._current_item:
            return

        title = self._current_item["title"]
        link = self._current_item["link"]
        if title and link:
            self.items.append(
                NewsItem(
                    title=title,
                    link=link,
                    summary=self._current_item["summary"],
                    published=self._current_item["published"],
                )
            )

        self._current_item = None


def collect_language_learning_news(
    source_url: str = BBC_FRENCH_NEWS_SOURCE,
    articles_count: int = 3,
    paragraphs_per_article: int = 3,
    output_file: str | Path | None = None,
) -> list[dict[str, str]]:
    """Collect longer news records suitable for language learning.

    By default this uses the BBC Afrique French-language World Service page.
    Each returned record contains:
        - date
        - link
        - name
        - info

    Args:
        source_url: HTTPS RSS/Atom feed URL or BBC World Service language page.
        articles_count: Number of articles to return.
        paragraphs_per_article: Number of article paragraphs to combine.
        output_file: Optional path where a readable text version is saved.

    Returns:
        A list of dictionaries with date, link, name, and info.
    """

    if articles_count < 1:
        raise ValueError("articles_count must be at least 1")
    if paragraphs_per_article < 1:
        raise ValueError("paragraphs_per_article must be at least 1")

    _validate_secure_url(source_url)
    source_content = _fetch_secure_feed(source_url)
    news_items = _parse_news_source(source_content)[:articles_count]
    records = [_build_language_learning_record(item, paragraphs_per_article) for item in news_items]

    if output_file is not None:
        _save_news_text(format_language_learning_news(records), output_file)

    return records


def format_language_learning_news(records: list[dict[str, str]]) -> str:
    """Format language-learning news records as readable text."""

    if not records:
        return "No language-learning news records were found."

    lines: list[str] = []
    for index, record in enumerate(records, start=1):
        lines.append(f"{index}. {record['name']}")
        lines.append(f"Date: {record['date']}")
        lines.append(f"Link: {record['link']}")
        lines.append("")
        lines.append(record["info"])
        lines.append("")

    return "\n".join(lines).strip()


def _parse_news_source(source_content: bytes) -> list[NewsItem]:
    try:
        return list(_parse_feed(source_content))
    except RuntimeError:
        return _parse_bbc_world_service_page(source_content)


def _parse_bbc_world_service_page(source_content: bytes) -> list[NewsItem]:
    parser = BBCWorldServiceHTMLParser()
    parser.feed(source_content.decode("utf-8", errors="ignore"))
    parser.close()
    return parser.items


def _build_language_learning_record(item: NewsItem, paragraphs_per_article: int) -> dict[str, str]:
    clean_link = _clean_article_link(item.link)
    raw_paragraphs = _extract_article_paragraphs(clean_link, paragraphs_per_article * 4)
    paragraphs = _select_learning_paragraphs(raw_paragraphs, paragraphs_per_article)
    info = "\n\n".join(paragraphs)

    if not info and item.summary:
        info = item.summary

    return {
        "date": item.published,
        "link": clean_link,
        "name": item.title,
        "info": info,
    }


def _clean_article_link(link: str) -> str:
    if "?at_medium=RSS" in link:
        return link.split("?", 1)[0]
    return link


def _select_learning_paragraphs(paragraphs: list[str], limit: int) -> list[str]:
    selected = []

    for paragraph in paragraphs:
        normalized = paragraph.strip()
        if not normalized:
            continue
        if len(normalized) < 80:
            continue
        if normalized.lower().startswith(SKIPPED_PARAGRAPH_PREFIXES):
            continue

        selected.append(normalized)
        if len(selected) == limit:
            break

    return selected
