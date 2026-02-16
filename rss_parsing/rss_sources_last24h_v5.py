from __future__ import annotations

"""
RSS last-24-hours collector (DB mode).

How to run:
  1) Install deps:
     pip install requests feedparser python-dateutil psycopg2-binary python-dotenv
  2) Ensure SUPABASE_DATABASE_URL is set in .env (full Postgres URL with ?sslmode=require).
  3) Run:
     python rss_sources_last24h_v3.py --window-hours 24

Optional flags:
  --debug
  --window-hours 24
  --max-items-per-feed 100
  --dry-run
  --limit-sources N
"""

import argparse
import calendar
import hashlib
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlparse, urlunparse, urlencode

import feedparser
import psycopg2
from psycopg2.extras import execute_values
import requests
from dateutil import parser as date_parser
from dotenv import load_dotenv

USER_AGENT = "threat-intel/0.1 (+https://localhost)"
REQUEST_TIMEOUT = 20
DEFAULT_WINDOW_HOURS = 24
DEFAULT_MAX_ITEMS = 100
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 2

FEED_EXTENSIONS = (".xml", ".rss", ".rdf", ".atom")
FEED_MARKERS = ("alt=rss", "format=rss", "/feed", "/feeds/", "rss.xml", "feed.xml")
INDEX_MARKERS = ("/tag/", "/tags/", "/category/", "/categories/", "/author/", "/search")
TRACKING_PARAMS_PREFIX = ("utm_",)
TRACKING_PARAMS_EXACT = {"gclid", "fbclid", "mc_cid", "mc_eid"}


@dataclass(frozen=True)
class FeedConfig:
    source_uuid: str
    source_name: str
    source_url: str
    url_scraping_method: str


@dataclass
class FetchResult:
    ok: bool
    status_code: str
    message: str
    content: bytes | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RSS last-24-hours collector (DB mode).")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--window-hours", type=int, default=DEFAULT_WINDOW_HOURS)
    parser.add_argument("--max-items-per-feed", type=int, default=DEFAULT_MAX_ITEMS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit-sources", type=int, default=0)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--backoff", type=int, default=DEFAULT_BACKOFF_SECONDS)
    return parser.parse_args()


def setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")


def load_env() -> None:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")
    load_dotenv(project_root / "connectors" / ".env", override=False)
    load_dotenv(project_root / "threat_intel" / ".env", override=False)


def get_db_conn():
    db_url = os.getenv("SUPABASE_DATABASE_URL")
    if not db_url:
        logging.error("SUPABASE_DATABASE_URL not found in environment.")
        sys.exit(1)
    return psycopg2.connect(db_url)


def fetch_feed(url: str, retries: int, backoff_seconds: int) -> FetchResult:
    attempt = 0
    while True:
        attempt += 1
        try:
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
        except requests.Timeout:
            if attempt <= retries:
                time.sleep(backoff_seconds * attempt)
                continue
            return FetchResult(False, "CONNECTION_TIMEOUT", "Timeout", None)
        except requests.exceptions.SSLError as exc:
            return FetchResult(False, "SSL_ERROR", f"SSL error: {exc}", None)
        except requests.exceptions.ConnectionError as exc:
            message = str(exc).lower()
            if "name or service not known" in message or "nodename nor servname" in message:
                return FetchResult(False, "DNS_ERROR", f"DNS error: {exc}", None)
            if attempt <= retries:
                time.sleep(backoff_seconds * attempt)
                continue
            return FetchResult(False, "CONNECTION_REFUSED", f"Connection error: {exc}", None)
        except requests.RequestException as exc:
            if attempt <= retries:
                time.sleep(backoff_seconds * attempt)
                continue
            return FetchResult(False, "UNKNOWN_ERROR", f"Request error: {exc}", None)

        if response.status_code in (429, 500, 502, 503, 504) and attempt <= retries:
            time.sleep(backoff_seconds * attempt)
            continue
        if response.status_code == 403:
            return FetchResult(False, "HTTP_403_FORBIDDEN", "HTTP 403", response.content)
        if response.status_code == 404:
            return FetchResult(False, "HTTP_404_NOT_FOUND", "HTTP 404", response.content)
        if response.status_code == 401:
            return FetchResult(False, "HTTP_401_UNAUTHORIZED", "HTTP 401", response.content)
        if response.status_code == 429:
            return FetchResult(False, "HTTP_429_TOO_MANY_REQUESTS", "HTTP 429", response.content)
        if 500 <= response.status_code <= 599:
            return FetchResult(False, "HTTP_5XX_SERVER_ERROR", f"HTTP {response.status_code}", response.content)
        if response.status_code != 200:
            return FetchResult(False, "UNKNOWN_ERROR", f"HTTP {response.status_code}", response.content)

        content_type = (response.headers.get("Content-Type") or "").lower()
        if content_type and not any(token in content_type for token in ("xml", "rss", "atom")):
            return FetchResult(False, "INVALID_CONTENT_TYPE", f"Content-Type {content_type}", response.content)

        return FetchResult(True, "OK", "OK", response.content)


def parse_feed(content: bytes) -> tuple[dict, list, str]:
    parsed = feedparser.parse(content)
    error_message = ""
    if getattr(parsed, "bozo", False):
        exception = getattr(parsed, "bozo_exception", None)
        if exception:
            error_message = f"bozo_exception: {exception}"
    return parsed.feed, parsed.entries, error_message


def extract_entry_datetime(entry: dict) -> tuple[datetime | None, str, list[str]]:
    notes: list[str] = []
    raw = ""

    struct_time = (
        entry.get("published_parsed")
        or entry.get("updated_parsed")
        or entry.get("created_parsed")
    )
    if struct_time:
        try:
            dt = datetime.fromtimestamp(calendar.timegm(struct_time), tz=timezone.utc)
            return dt, raw, notes
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
            return dt, raw, notes
        except Exception:
            notes.append("date_parse_error")

    return None, raw, ["missing_date"]


def normalize_url(url: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if parsed.netloc != netloc:
        notes.append("lowercased_host")

    if (scheme == "http" and netloc.endswith(":80")) or (scheme == "https" and netloc.endswith(":443")):
        netloc = netloc.rsplit(":", 1)[0]
        notes.append("normalized_default_port")

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
        notes.append("normalized_trailing_slash")

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    filtered = []
    removed = False
    for key, value in query_pairs:
        key_lower = key.lower()
        if key_lower.startswith(TRACKING_PARAMS_PREFIX) or key_lower in TRACKING_PARAMS_EXACT:
            removed = True
            continue
        filtered.append((key, value))
    if removed:
        notes.append("removed_tracking_params")

    fragment = parsed.fragment
    if fragment:
        notes.append("removed_fragment")

    normalized = urlunparse((scheme, netloc, path, "", urlencode(filtered, doseq=True), ""))
    return normalized, notes


def validate_url(url: str, source_url: str) -> tuple[bool, list[str]]:
    notes: list[str] = []
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
    return True, notes


def resolve_redirects(url: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    try:
        response = requests.head(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        final_url = response.url
        response.close()
        if response.status_code in (405, 403):
            raise requests.RequestException("HEAD not allowed")
        if final_url != url:
            notes.append("resolved_redirects")
        return final_url, notes
    except requests.RequestException:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
                stream=True,
            )
            final_url = response.url
            response.close()
            if final_url != url:
                notes.append("resolved_redirects")
            return final_url, notes
        except requests.RequestException as exc:
            return url, [f"redirect_failed:{exc}"]


def compute_article_uuid(canonical_final_url: str) -> str:
    digest = hashlib.sha256(canonical_final_url.encode("utf-8")).hexdigest()[:16]
    return f"A_{digest}"


def get_sources(conn, limit: int) -> list[FeedConfig]:
    sql = """
        SELECT source_uuid, source_name, source_url, url_scraping_method
        FROM sources_master_list
        WHERE is_active = true
          AND source = 'Website'
          AND url_scraping_method = 'RSS'
        ORDER BY source_number ASC
    """
    if limit > 0:
        sql += " LIMIT %s"
        params = (limit,)
    else:
        params = ()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [FeedConfig(*row) for row in rows]


def update_source_status(
    conn,
    source_uuid: str,
    status: str,
    status_code: str,
    now_utc: datetime,
    update_last_ok: bool,
    dry_run: bool,
) -> None:
    if dry_run:
        return
    if update_last_ok:
        sql = """
            UPDATE sources_master_list
            SET status = %s,
                status_code = %s,
                last_ok_status_utc_iso = %s
            WHERE source_uuid = %s
        """
        params = (status, status_code, now_utc, source_uuid)
    else:
        sql = """
            UPDATE sources_master_list
            SET status = %s,
                status_code = %s
            WHERE source_uuid = %s
        """
        params = (status, status_code, source_uuid)
    with conn.cursor() as cur:
        cur.execute(sql, params)


def insert_articles(
    conn,
    rows: list[tuple],
    dry_run: bool,
) -> int:
    if dry_run or not rows:
        return 0
    sql = """
        INSERT INTO extracted_article_urls (
            article_uuid,
            source_uuid,
            url_scraping_method,
            source_url,
            article_title,
            article_url_original,
            article_url_final,
            url_original_to_final_match,
            url_notes,
            published_utc_iso,
            article_detected_utc_iso,
            created_at
        ) VALUES %s
        ON CONFLICT (article_uuid) DO NOTHING
        RETURNING 1
    """
    with conn.cursor() as cur:
        returned = execute_values(cur, sql, rows, fetch=True)
        return len(returned) if returned else 0


def _open_db_conn():
    return get_db_conn()


def main() -> None:
    args = parse_args()
    setup_logging(args.debug)
    load_env()

    now_utc = datetime.now(tz=timezone.utc)
    window_start = now_utc - timedelta(hours=args.window_hours)

    conn = _open_db_conn()
    conn.autocommit = False
    try:
        sources = get_sources(conn, args.limit_sources)
        if not sources:
            logging.error("No active RSS sources found.")
            return

        for source in sources:
            logging.info(
                "Processing source: %s | %s | %s",
                source.source_uuid,
                source.source_name,
                source.source_url,
            )
            inserted_count = 0
            deduped_count = 0
            items_total = 0
            items_with_dates = 0
            items_in_window = 0

            try:
                fetch_result = fetch_feed(source.source_url, args.retries, args.backoff)
                if not fetch_result.ok:
                    update_source_status(
                        conn,
                        source.source_uuid,
                        "ERROR",
                        fetch_result.status_code,
                        now_utc,
                        update_last_ok=False,
                        dry_run=args.dry_run,
                    )
                    if not args.dry_run:
                        conn.commit()
                    logging.warning(
                        "Fetch failed: %s | %s", fetch_result.status_code, fetch_result.message
                    )
                    continue

                feed_meta, entries, parse_warn = parse_feed(fetch_result.content or b"")
                if parse_warn:
                    status_code = "PARSING_ERROR"
                else:
                    status_code = "OK"

                rows_to_insert: list[tuple] = []
                for entry in entries[: args.max_items_per_feed]:
                    items_total += 1
                    published_dt, published_raw, dt_notes = extract_entry_datetime(entry)
                    if published_dt is None:
                        continue
                    items_with_dates += 1
                    published_utc = published_dt.astimezone(timezone.utc)
                    if not (window_start <= published_utc <= now_utc):
                        continue
                    items_in_window += 1

                    url_original = entry.get("link") or entry.get("id") or entry.get("guid") or ""
                    if not url_original:
                        continue
                    if not url_original.startswith(("http://", "https://")):
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

                    url_notes_all = dt_notes + url_notes + norm_notes + redirect_notes + final_notes + final_url_notes
                    url_notes = ",".join(sorted(set(n for n in url_notes_all if n)))

                    article_uuid = compute_article_uuid(canonical_final)
                    url_match = url_original == canonical_final

                    title = entry.get("title")
                    if isinstance(title, str):
                        title = title.strip() or None
                    else:
                        title = None

                    rows_to_insert.append(
                        (
                            article_uuid,
                            source.source_uuid,
                            source.url_scraping_method,
                            source.source_url,
                            title,
                            url_original,
                            canonical_final,
                            url_match,
                            url_notes if url_notes else None,
                            published_utc,
                            now_utc,
                            now_utc,
                        )
                    )

                inserted_count = insert_articles(conn, rows_to_insert, args.dry_run)
                deduped_count = max(0, len(rows_to_insert) - inserted_count)

                if items_in_window == 0:
                    status_code = "NO_RECENT_ARTICLES"
                if parse_warn:
                    status_code = "PARSING_ERROR"

                update_source_status(
                    conn,
                    source.source_uuid,
                    "OK",
                    status_code,
                    now_utc,
                    update_last_ok=True,
                    dry_run=args.dry_run,
                )
                if not args.dry_run:
                    conn.commit()

                logging.info(
                    "source_uuid=%s source_url=%s status_code=%s items_total=%s items_with_dates=%s items_in_window=%s inserted=%s deduped=%s",
                    source.source_uuid,
                    source.source_url,
                    status_code,
                    items_total,
                    items_with_dates,
                    items_in_window,
                    inserted_count,
                    deduped_count,
                )
            except psycopg2.OperationalError as exc:
                conn.rollback()
                logging.warning("DB connection dropped, reopening: %s", exc)
                conn.close()
                conn = _open_db_conn()
                conn.autocommit = False
                try:
                    update_source_status(
                        conn,
                        source.source_uuid,
                        "ERROR",
                        "UNKNOWN_ERROR",
                        now_utc,
                        update_last_ok=False,
                        dry_run=args.dry_run,
                    )
                    if not args.dry_run:
                        conn.commit()
                except Exception:
                    conn.rollback()
            except Exception as exc:
                conn.rollback()
                logging.exception("Error processing source %s", source.source_uuid)
                update_source_status(
                    conn,
                    source.source_uuid,
                    "ERROR",
                    "UNKNOWN_ERROR",
                    now_utc,
                    update_last_ok=False,
                    dry_run=args.dry_run,
                )
                if not args.dry_run:
                    conn.commit()

    finally:
        conn.close()


if __name__ == "__main__":
    main()
