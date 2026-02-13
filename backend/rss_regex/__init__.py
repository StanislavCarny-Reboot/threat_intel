"""
RSS Regex Processing Package

Three-script workflow for processing RSS feeds using regex patterns:
1. parse_rss_feeds.py - Extract article links from RSS feeds
2. fetch_article_content.py - Fetch content and track HTTP status
3. clean_articles.py - Clean article content using source-specific patterns
"""

from rss_regex.config.source_patterns import (
    get_source_config,
    SOURCE_REGISTRY,
    SourceConfig,
    RssParsePatterns,
    ContentCleanPatterns,
)

__all__ = [
    "get_source_config",
    "SOURCE_REGISTRY",
    "SourceConfig",
    "RssParsePatterns",
    "ContentCleanPatterns",
]
