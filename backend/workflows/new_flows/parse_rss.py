"""RSS last-24-hours URL collector - Prefect flow."""

from __future__ import annotations

import calendar
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
import requests
from dateutil import parser as date_parser
from loguru import logger
from prefect import flow, task
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from tenacity import retry, stop_after_attempt, wait_fixed

from connectors.database import get_sync_db_session
from models.entities import ExtractedArticleUrl, SourceErrorLog, SourcesMasterList

# --- Constants ---
USER_AGENT = "threat-intel/0.1 (+https://localhost)"
REQUEST_TIMEOUT = 20
DEFAULT_WINDOW_HOURS = 24
DEFAULT_MAX_ITEMS = 100

FEED_EXTENSIONS = (".xml", ".rss", ".rdf", ".atom")
FEED_MARKERS = ("alt=rss", "format=rss", "/feed", "/feeds/", "rss.xml", "feed.xml")
INDEX_MARKERS = ("/tag/", "/tags/", "/category/", "/categories/", "/author/", "/search")
TRACKING_PARAMS_PREFIX = ("utm_",)
TRACKING_PARAMS_EXACT = {"gclid", "fbclid", "mc_cid", "mc_eid"}

_HTTP_ERROR_MAP = {
    401: ("HTTP_401_UNAUTHORIZED", "HTTP 401"),
    403: ("HTTP_403_FORBIDDEN", "HTTP 403"),
    404: ("HTTP_404_NOT_FOUND", "HTTP 404"),
    429: ("HTTP_429_TOO_MANY_REQUESTS", "HTTP 429"),
}


@dataclass
class FetchResult:
    ok: bool
    status_code: str
    message: str
    content: bytes | None


# --- URL Utilities (pure functions) ---


def normalize_url(url: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    if parsed.netloc != netloc:
        notes.append("lowercased_host")
    if (scheme == "http" and netloc.endswith(":80")) or (
        scheme == "https" and netloc.endswith(":443")
    ):
        netloc = netloc.rsplit(":", 1)[0]
        notes.append("normalized_default_port")

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
        notes.append("normalized_trailing_slash")

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    filtered, removed = [], False
    for key, value in query_pairs:
        key_lower = key.lower()
        if (
            key_lower.startswith(TRACKING_PARAMS_PREFIX)
            or key_lower in TRACKING_PARAMS_EXACT
        ):
            removed = True
            continue
        filtered.append((key, value))

    if removed:
        notes.append("removed_tracking_params")
    if parsed.fragment:
        notes.append("removed_fragment")

    return (
        urlunparse((scheme, netloc, path, "", urlencode(filtered, doseq=True), "")),
        notes,
    )


def validate_url(url: str, source_url: str) -> tuple[bool, list[str]]:
    if not url.startswith(("http://", "https://")):
        return False, ["invalid_scheme"]
    if url == source_url:
        return False, ["same_as_feed_url"]
    lower_url = url.lower()
    if lower_url.endswith(FEED_EXTENSIONS):
        return False, ["feed_extension"]
    if any(marker in lower_url for marker in FEED_MARKERS):
        return False, ["feed_marker"]
    if any(marker in urlparse(url).path.lower() for marker in INDEX_MARKERS):
        return False, ["index_like_url"]
    return True, []


def compute_article_uuid(canonical_url: str) -> str:
    digest = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]
    return f"A_{digest}"


def extract_entry_datetime(entry: dict) -> tuple[datetime | None, list[str]]:
    notes: list[str] = []

    struct_time = (
        entry.get("published_parsed")
        or entry.get("updated_parsed")
        or entry.get("created_parsed")
    )
    if struct_time:
        try:
            return (
                datetime.fromtimestamp(calendar.timegm(struct_time), tz=timezone.utc),
                notes,
            )
        except Exception:
            notes.append("struct_time_parse_error")

    raw = (
        entry.get("published")
        or entry.get("updated")
        or entry.get("created")
        or entry.get("date")
        or ""
    )
    if raw:
        try:
            dt = date_parser.parse(raw)
            if dt.tzinfo is None:
                notes.append("assumed_utc_no_tz")
                dt = dt.replace(tzinfo=timezone.utc)
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw.strip()):
                notes.append("date_only_assumed_midnight")
                dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            return dt, notes
        except Exception:
            notes.append("date_parse_error")

    return None, ["missing_date"]


# --- HTTP Helpers ---


@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
def _http_get(url: str, **kwargs) -> requests.Response:
    return requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
        **kwargs,
    )


def fetch_feed(url: str) -> FetchResult:
    """Fetch RSS feed bytes from URL with retry."""
    try:
        response = _http_get(url)
    except requests.Timeout:
        return FetchResult(False, "CONNECTION_TIMEOUT", "Timeout", None)
    except requests.exceptions.SSLError as exc:
        return FetchResult(False, "SSL_ERROR", f"SSL error: {exc}", None)
    except requests.exceptions.ConnectionError as exc:
        msg = str(exc).lower()
        code = (
            "DNS_ERROR"
            if ("name or service not known" in msg or "nodename nor servname" in msg)
            else "CONNECTION_REFUSED"
        )
        return FetchResult(False, code, f"Connection error: {exc}", None)
    except requests.RequestException as exc:
        return FetchResult(False, "UNKNOWN_ERROR", f"Request error: {exc}", None)

    if response.status_code in _HTTP_ERROR_MAP:
        code, msg = _HTTP_ERROR_MAP[response.status_code]
        return FetchResult(False, code, msg, response.content)
    if 500 <= response.status_code <= 599:
        return FetchResult(
            False,
            "HTTP_5XX_SERVER_ERROR",
            f"HTTP {response.status_code}",
            response.content,
        )
    if response.status_code != 200:
        return FetchResult(
            False, "UNKNOWN_ERROR", f"HTTP {response.status_code}", response.content
        )

    content_type = (response.headers.get("Content-Type") or "").lower()
    if content_type and not any(t in content_type for t in ("xml", "rss", "atom")):
        return FetchResult(
            False,
            "INVALID_CONTENT_TYPE",
            f"Content-Type {content_type}",
            response.content,
        )

    return FetchResult(True, "OK", "OK", response.content)


def resolve_redirects(url: str) -> tuple[str, list[str]]:
    """Follow HTTP redirects to get the final URL."""
    notes: list[str] = []
    try:
        resp = requests.head(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        if resp.status_code in (405, 403):
            raise requests.RequestException("HEAD not allowed")
        final_url = resp.url
        resp.close()
    except requests.RequestException:
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
                stream=True,
            )
            final_url = resp.url
            resp.close()
        except requests.RequestException as exc:
            return url, [f"redirect_failed:{exc}"]

    if final_url != url:
        notes.append("resolved_redirects")
    return final_url, notes


def parse_feed(content: bytes) -> tuple[list, str]:
    """Parse RSS feed bytes into a list of entries."""
    parsed = feedparser.parse(content)
    error_message = ""
    if getattr(parsed, "bozo", False) and getattr(parsed, "bozo_exception", None):
        error_message = f"bozo_exception: {parsed.bozo_exception}"
    return parsed.entries, error_message


def build_article_rows(
    entries: list,
    source: SourcesMasterList,
    now_utc: datetime,
    window_start: datetime,
    max_items: int,
) -> list[dict]:
    """Filter and transform feed entries into DB-ready row dicts."""
    rows: list[dict] = []

    for entry in entries[:max_items]:
        published_dt, dt_notes = extract_entry_datetime(entry)
        if published_dt is None:
            continue

        published_utc = published_dt.astimezone(timezone.utc)
        if not (window_start <= published_utc <= now_utc):
            continue

        url_original = entry.get("link") or entry.get("id") or entry.get("guid") or ""
        if not url_original or not url_original.startswith(("http://", "https://")):
            continue

        ok_url, url_notes = validate_url(url_original, source.source_url)
        if not ok_url:
            continue

        normalized_original, norm_notes = normalize_url(url_original)
        final_url, redirect_notes = resolve_redirects(normalized_original)
        canonical_final, final_notes = normalize_url(final_url)

        ok_final, final_url_notes = validate_url(canonical_final, source.source_url)
        if not ok_final:
            continue

        all_notes = (
            dt_notes
            + url_notes
            + norm_notes
            + redirect_notes
            + final_notes
            + final_url_notes
        )
        notes_str = ",".join(sorted(set(n for n in all_notes if n))) or None

        title_raw = entry.get("title")
        title = title_raw.strip() or None if isinstance(title_raw, str) else None

        rows.append(
            {
                "article_uuid": compute_article_uuid(canonical_final),
                "source_uuid": source.source_uuid,
                "url_scraping_method": source.url_scraping_method,
                "source_url": source.source_url,
                "article_title": title,
                "article_url_original": url_original,
                "article_url_final": canonical_final,
                "url_original_to_final_match": url_original == canonical_final,
                "url_notes": notes_str,
                "published_utc_iso": published_utc,
                "article_detected_utc_iso": now_utc,
                "created_at": now_utc,
            }
        )

    return rows


# --- DB Helpers ---


def _save_error_record(
    source: SourcesMasterList,
    status_code: str,
    error_message: str,
    now_utc: datetime,
    session,
) -> None:
    """Log a fetch failure to source_error_log."""
    record = SourceErrorLog(
        source_uuid=source.source_uuid,
        source_url=source.source_url,
        status_code=status_code,
        error_message=error_message,
        detected_at=now_utc,
        created_at=now_utc,
    )
    session.add(record)


def _save_articles(rows: list[dict], session) -> int:
    if not rows:
        return 0
    stmt = (
        pg_insert(ExtractedArticleUrl)
        .values(rows)
        .on_conflict_do_nothing(index_elements=[ExtractedArticleUrl.article_uuid])
    )
    result = session.execute(stmt)
    return result.rowcount or 0


def _update_source_status(
    source_uuid: str,
    status: str,
    status_code: str,
    now_utc: datetime,
    update_last_ok: bool,
    session,
) -> None:
    source = session.get(SourcesMasterList, source_uuid)
    if source is None:
        logger.warning("Source %s not found for status update", source_uuid)
        return
    source.status = status
    source.status_code = status_code
    if update_last_ok:
        source.last_ok_status_utc_iso = now_utc


# --- Prefect Tasks ---


@task(name="fetch-rss-sources", tags=["rss-db"])
def fetch_rss_sources(limit: int = 0) -> list[SourcesMasterList]:
    """Load active RSS sources from the database."""
    session = get_sync_db_session()
    try:
        query = (
            select(SourcesMasterList)
            .where(
                SourcesMasterList.is_active == True,  # noqa: E712
                SourcesMasterList.source == "Website",
                SourcesMasterList.url_scraping_method == "RSS",
            )
            .order_by(SourcesMasterList.source_number)
        )
        if limit > 0:
            query = query.limit(limit)
        return list(session.execute(query).scalars().all())
    finally:
        session.close()


@task(
    name="process-rss-source",
    task_run_name="process-{source.source_name}",
    retries=1,
    retry_delay_seconds=5,
    tags=["rss-processing"],
)
def process_source(
    source: SourcesMasterList,
    now_utc: datetime,
    window_start: datetime,
    max_items: int = DEFAULT_MAX_ITEMS,
    dry_run: bool = False,
) -> dict:
    """Fetch, parse, and store article URLs for a single RSS source."""
    session = get_sync_db_session()
    try:
        fetch_result = fetch_feed(source.source_url)
        if not fetch_result.ok:
            logger.warning(
                "Fetch failed for %s: %s - %s",
                source.source_url,
                fetch_result.status_code,
                fetch_result.message,
            )
            if not dry_run:
                _save_error_record(
                    source,
                    fetch_result.status_code,
                    fetch_result.message,
                    now_utc,
                    session,
                )
                session.commit()
            return {
                "source_uuid": source.source_uuid,
                "inserted": 0,
                "deduped": 0,
                "status_code": fetch_result.status_code,
            }

        entries, parse_warn = parse_feed(fetch_result.content or b"")
        rows = build_article_rows(entries, source, now_utc, window_start, max_items)

        if not rows:
            status_code = "PARSING_ERROR" if parse_warn else "NO_RECENT_ARTICLES"
        elif parse_warn:
            status_code = "PARSING_ERROR"
        else:
            status_code = "OK"

        inserted = 0
        if not dry_run:
            inserted = _save_articles(rows, session)
            _update_source_status(
                source.source_uuid, "OK", status_code, now_utc, True, session
            )
            session.commit()

        deduped = max(0, len(rows) - inserted)
        logger.info(
            "source_uuid=%s status_code=%s rows_built=%s inserted=%s deduped=%s",
            source.source_uuid,
            status_code,
            len(rows),
            inserted,
            deduped,
        )
        return {
            "source_uuid": source.source_uuid,
            "inserted": inserted,
            "deduped": deduped,
            "status_code": status_code,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --- Prefect Flow ---


@flow(name="rss-url-collector", log_prints=True)
def run(
    window_hours: int = DEFAULT_WINDOW_HOURS,
    max_items_per_feed: int = DEFAULT_MAX_ITEMS,
    limit_sources: int = 0,
    dry_run: bool = False,
) -> None:
    """Collect RSS article URLs published within the last `window_hours` hours."""
    now_utc = datetime.now(tz=timezone.utc)
    window_start = now_utc - timedelta(hours=window_hours)

    sources = fetch_rss_sources(limit_sources)
    if not sources:
        logger.error("No active RSS sources found.")
        return

    logger.info("Found %d RSS sources to process", len(sources))

    futures = [
        process_source.submit(
            source, now_utc, window_start, max_items_per_feed, dry_run
        )
        for source in sources
    ]
    results = [f.result(raise_on_failure=False) for f in futures]

    total_inserted = sum(r.get("inserted", 0) for r in results if isinstance(r, dict))
    successful = sum(1 for r in results if isinstance(r, dict))
    logger.info(
        "Completed: %d sources, %d successful, %d articles inserted",
        len(sources),
        successful,
        total_inserted,
    )


if __name__ == "__main__":
    run.serve()
