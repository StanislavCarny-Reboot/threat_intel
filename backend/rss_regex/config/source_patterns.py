"""
Regex pattern registry for RSS source-specific parsing and cleaning.

Each source has two pattern sets:
1. rss_patterns: For parsing RSS feed XML to extract article links
2. clean_patterns: For cleaning article content (removing headers/footers)
"""

from dataclasses import dataclass, field
from typing import Pattern
import re


@dataclass
class RssParsePatterns:
    """Patterns for extracting article URLs from RSS feeds."""

    # Pattern to match article item blocks
    item_pattern: Pattern
    # Pattern to extract URL from within an item block
    url_pattern: Pattern
    # Pattern to extract title from within an item block
    title_pattern: Pattern
    # Pattern to extract publication date
    date_pattern: Pattern
    # Date format string for parsing (strptime format)
    date_format: str = "%a, %d %b %Y %H:%M:%S %z"


@dataclass
class ContentCleanPatterns:
    """Patterns for cleaning article content."""

    # Patterns to remove from beginning (headers, nav, etc.)
    header_patterns: list[Pattern] = field(default_factory=list)
    # Patterns to remove from end (footers, related articles, etc.)
    footer_patterns: list[Pattern] = field(default_factory=list)
    # Patterns to remove throughout (ads, social buttons, etc.)
    remove_patterns: list[Pattern] = field(default_factory=list)
    # Pattern to extract main content area (optional)
    main_content_pattern: Pattern | None = None


@dataclass
class SourceConfig:
    """Complete configuration for a single RSS source."""

    name: str
    rss_patterns: RssParsePatterns
    clean_patterns: ContentCleanPatterns
    # Whether this source uses standard RSS/Atom format
    is_standard_feed: bool = True


# ============================================================
# GENERIC PATTERNS (fallback for unknown sources)
# ============================================================

GENERIC_RSS_PATTERNS = RssParsePatterns(
    item_pattern=re.compile(r"<item>(.*?)</item>", re.DOTALL | re.IGNORECASE),
    url_pattern=re.compile(r"<link>([^<]+)</link>", re.IGNORECASE),
    title_pattern=re.compile(
        r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.DOTALL | re.IGNORECASE
    ),
    date_pattern=re.compile(r"<pubDate>([^<]+)</pubDate>", re.IGNORECASE),
    date_format="%a, %d %b %Y %H:%M:%S %z",
)

GENERIC_ATOM_PATTERNS = RssParsePatterns(
    item_pattern=re.compile(r"<entry>(.*?)</entry>", re.DOTALL | re.IGNORECASE),
    url_pattern=re.compile(r'<link[^>]*href=["\']([^"\']+)["\']', re.IGNORECASE),
    title_pattern=re.compile(
        r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>",
        re.DOTALL | re.IGNORECASE,
    ),
    date_pattern=re.compile(
        r"<(?:published|updated)>([^<]+)</(?:published|updated)>", re.IGNORECASE
    ),
    date_format="%Y-%m-%dT%H:%M:%S%z",
)

GENERIC_CLEAN_PATTERNS = ContentCleanPatterns(
    header_patterns=[],
    footer_patterns=[
        re.compile(
            r"(?:Related Articles|Read More|Share this).*$",
            re.DOTALL | re.IGNORECASE,
        ),
    ],
    remove_patterns=[
        re.compile(r"Advertisement", re.IGNORECASE),
        re.compile(r"Subscribe to our newsletter.*?\n", re.IGNORECASE),
    ],
)


# ============================================================
# SOURCE-SPECIFIC CONFIGURATIONS
# ============================================================

# The Hacker News
THEHACKERNEWS_PATTERNS = RssParsePatterns(
    item_pattern=re.compile(r"<item>(.*?)</item>", re.DOTALL | re.IGNORECASE),
    url_pattern=re.compile(
        r"<link>([^<]*thehackernews\.com/\d{4}/\d{2}/[^<]*)</link>", re.IGNORECASE
    ),
    title_pattern=re.compile(
        r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.DOTALL | re.IGNORECASE
    ),
    date_pattern=re.compile(r"<pubDate>([^<]+)</pubDate>", re.IGNORECASE),
    date_format="%a, %d %b %Y %H:%M:%S %z",
)

THEHACKERNEWS_CLEAN = ContentCleanPatterns(
    header_patterns=[],
    footer_patterns=[
        re.compile(
            r"Found this article interesting\?.*$", re.DOTALL | re.IGNORECASE
        ),
        re.compile(r"Follow us on Twitter.*$", re.DOTALL | re.IGNORECASE),
    ],
    remove_patterns=[
        re.compile(r"SHARE\s+SHARE\s+TWEET", re.IGNORECASE),
    ],
)

# Bleeping Computer
BLEEPINGCOMPUTER_PATTERNS = RssParsePatterns(
    item_pattern=re.compile(r"<item>(.*?)</item>", re.DOTALL | re.IGNORECASE),
    url_pattern=re.compile(
        r"<link>([^<]*bleepingcomputer\.com/news/[^<]*)</link>", re.IGNORECASE
    ),
    title_pattern=re.compile(
        r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.DOTALL | re.IGNORECASE
    ),
    date_pattern=re.compile(r"<pubDate>([^<]+)</pubDate>", re.IGNORECASE),
    date_format="%a, %d %b %Y %H:%M:%S %Z",
)

BLEEPINGCOMPUTER_CLEAN = ContentCleanPatterns(
    header_patterns=[],
    footer_patterns=[
        re.compile(r"Related Articles:.*$", re.DOTALL | re.IGNORECASE),
    ],
    remove_patterns=[
        re.compile(r"Not a member yet\?.*?Register Now", re.DOTALL | re.IGNORECASE),
    ],
)

# Krebs on Security
KREBSONSECURITY_PATTERNS = RssParsePatterns(
    item_pattern=re.compile(r"<item>(.*?)</item>", re.DOTALL | re.IGNORECASE),
    url_pattern=re.compile(
        r"<link>([^<]*krebsonsecurity\.com/\d{4}/\d{2}/[^<]*)</link>", re.IGNORECASE
    ),
    title_pattern=re.compile(
        r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.DOTALL | re.IGNORECASE
    ),
    date_pattern=re.compile(r"<pubDate>([^<]+)</pubDate>", re.IGNORECASE),
    date_format="%a, %d %b %Y %H:%M:%S %z",
)

KREBSONSECURITY_CLEAN = ContentCleanPatterns(
    header_patterns=[],
    footer_patterns=[
        re.compile(r"This entry was posted.*$", re.DOTALL | re.IGNORECASE),
        re.compile(r"Tags:.*$", re.DOTALL | re.IGNORECASE),
    ],
    remove_patterns=[],
)

# Dark Reading
DARKREADING_PATTERNS = RssParsePatterns(
    item_pattern=re.compile(r"<item>(.*?)</item>", re.DOTALL | re.IGNORECASE),
    url_pattern=re.compile(
        r"<link>([^<]*darkreading\.com/[^<]*)</link>", re.IGNORECASE
    ),
    title_pattern=re.compile(
        r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.DOTALL | re.IGNORECASE
    ),
    date_pattern=re.compile(r"<pubDate>([^<]+)</pubDate>", re.IGNORECASE),
    date_format="%a, %d %b %Y %H:%M:%S %z",
)

DARKREADING_CLEAN = ContentCleanPatterns(
    header_patterns=[],
    footer_patterns=[
        re.compile(r"About the Author.*$", re.DOTALL | re.IGNORECASE),
        re.compile(r"Related:.*$", re.DOTALL | re.IGNORECASE),
    ],
    remove_patterns=[],
)


# ============================================================
# MAIN REGISTRY - Maps source names to their configurations
# ============================================================

SOURCE_REGISTRY: dict[str, SourceConfig] = {
    "thehackernews": SourceConfig(
        name="The Hacker News",
        rss_patterns=THEHACKERNEWS_PATTERNS,
        clean_patterns=THEHACKERNEWS_CLEAN,
    ),
    "the hacker news": SourceConfig(
        name="The Hacker News",
        rss_patterns=THEHACKERNEWS_PATTERNS,
        clean_patterns=THEHACKERNEWS_CLEAN,
    ),
    "bleepingcomputer": SourceConfig(
        name="Bleeping Computer",
        rss_patterns=BLEEPINGCOMPUTER_PATTERNS,
        clean_patterns=BLEEPINGCOMPUTER_CLEAN,
    ),
    "bleeping computer": SourceConfig(
        name="Bleeping Computer",
        rss_patterns=BLEEPINGCOMPUTER_PATTERNS,
        clean_patterns=BLEEPINGCOMPUTER_CLEAN,
    ),
    "krebsonsecurity": SourceConfig(
        name="Krebs on Security",
        rss_patterns=KREBSONSECURITY_PATTERNS,
        clean_patterns=KREBSONSECURITY_CLEAN,
    ),
    "krebs on security": SourceConfig(
        name="Krebs on Security",
        rss_patterns=KREBSONSECURITY_PATTERNS,
        clean_patterns=KREBSONSECURITY_CLEAN,
    ),
    "darkreading": SourceConfig(
        name="Dark Reading",
        rss_patterns=DARKREADING_PATTERNS,
        clean_patterns=DARKREADING_CLEAN,
    ),
    "dark reading": SourceConfig(
        name="Dark Reading",
        rss_patterns=DARKREADING_PATTERNS,
        clean_patterns=DARKREADING_CLEAN,
    ),
}

# Default configurations for unknown sources
DEFAULT_RSS_CONFIG = SourceConfig(
    name="Generic RSS",
    rss_patterns=GENERIC_RSS_PATTERNS,
    clean_patterns=GENERIC_CLEAN_PATTERNS,
)

DEFAULT_ATOM_CONFIG = SourceConfig(
    name="Generic Atom",
    rss_patterns=GENERIC_ATOM_PATTERNS,
    clean_patterns=GENERIC_CLEAN_PATTERNS,
)


def get_source_config(source_name: str) -> SourceConfig:
    """
    Get configuration for a source by name.
    Falls back to generic RSS patterns if source not found.
    """
    # Normalize source name for lookup
    key = source_name.lower().strip()
    return SOURCE_REGISTRY.get(key, DEFAULT_RSS_CONFIG)


def detect_feed_type(content: str) -> str:
    """Detect whether feed is RSS or Atom format."""
    if "<feed" in content.lower() and 'xmlns="http://www.w3.org/2005/Atom"' in content:
        return "atom"
    return "rss"
