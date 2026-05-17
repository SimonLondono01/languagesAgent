"""News collection helpers for research articles."""

from .article_paragraph_collector import collect_article_paragraphs
from .language_learning_news import collect_language_learning_news
from .news_collector import collect_news

__all__ = ["collect_article_paragraphs", "collect_language_learning_news", "collect_news"]
