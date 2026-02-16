# extracted_articles_urls (Supabase/Postgres)

Table 2: extracted_article_urls
Description
extracted_article_urls stores the article URLs discovered during the daily source scan. Each day, the pipeline visits every source from sources_master_list (RSS and non-RSS) and identifies articles published within the last 24 hours. Newly discovered articles are inserted here so downstream phases can scrape full article content (stored in a separate table later).
This table is cumulative: it contains URLs discovered today and on previous days. It represents the “URL discovery ledger” for the pipeline.
Role in the pipeline
Source scan (daily)


Read active sources from sources_master_list


Discover articles published within the last 24 hours


Normalize/resolve URLs and store discovery results in extracted_article_urls


Article scraping (later phase)


Read unscripted/unprocessed article URLs from extracted_article_urls


Fetch page content, extract text/metadata, and store results in a separate scraped_articles-type table (to be documented later)



Primary key and identity strategy
article_uuid (Primary Key)
Purpose: provide a stable identifier for a unique article, supporting cross-source deduplication (the same final article URL linked by multiple sources should map to the same article_uuid).
Recommended format (global, URL-based):
article_uuid = "A_" + <hash16>


Example: A_7f3c2a9f6c1b8d02


How <hash16> is generated:
Start with article_url_original (as found on the source page/feed).


Resolve redirects to derive article_url_final.


Normalize/canonicalize article_url_final consistently (see “Original vs Final URL handling”).


Compute sha256(canonical_final_url) as a hex string.


Use the first 16 hex characters of that digest as hash16.


This yields a short, stable ID with very low collision risk at your expected scale.

Original vs Final URL handling
Why two URL fields?
Sources often provide URLs that:
redirect to another URL,


include tracking parameters (utm_*, gclid, etc.),


include fragments (#section),


differ slightly due to canonicalization (trailing slash, casing).


To support consistent dedupe and clean downstream scraping, the pipeline stores both the original extracted URL and the final canonical URL.
Canonicalization rules (minimum recommended)
When producing article_url_final, the script should:
follow HTTP redirects to the final destination,


remove URL fragments (#...),


remove common tracking parameters: utm_*, gclid, fbclid, mc_cid, mc_eid (extendable),


normalize scheme/host casing (lowercase host is typical),


normalize default ports (:80, :443) if present,


standardize trailing slash handling consistently.


Any transformations applied should be recorded in url_notes.

Columns
Identity and linkage
article_uuid (text, Primary Key)
 Unique article identifier computed from canonical final URL: A_<hash16>.


source_uuid (text, Foreign Key → sources_master_list.source_uuid)
 Identifies the source that produced/discovered this article URL during the daily scan.


url_scraping_method (text)
 Copied from the source record (e.g., RSS, Direct). Stored here to simplify debugging and analysis.


source_url (text)
Copied from the source record. This is the URL that was visited to discover the article (RSS feed URL or direct page URL).



Article discovery fields
article_title (text, nullable)
 Title/headline if extractable from the source listing/feed.
 Preferred approach: store NULL when not available (rather than N/A) to keep filtering/querying clean.


article_url_original (text, not null)
 URL as extracted from the source listing or feed. May contain tracking parameters and/or redirect.


article_url_final (text, not null)
 Canonical final URL after redirect resolution + normalization. Used as the canonical reference for scraping and for generating article_uuid.


url_original_to_final_match (boolean, not null)
 TRUE if article_url_original equals article_url_final after normalization rules are applied, otherwise FALSE.


url_notes (text, nullable)
 Notes explaining how article_url_original was transformed into article_url_final.
 Recommended standardized tokens (comma-separated if multiple):


resolved_redirects


removed_tracking_params


removed_fragment


normalized_trailing_slash


lowercased_host


other_normalization



Publishing metadata
published_utc_iso (timestamptz, nullable)
Publication timestamp, expressed in UTC, if available from the source metadata (RSS fields, JSON-LD, HTML time tags, etc.).
If the source only provides a date (no time), you may store the timestamp as 00:00:00Z on that date (consistent convention).



Discovery tracking metadata
Because article_uuid is derived from the canonical final URL and enforced as unique, duplicate discoveries of the same article are prevented at insert time (via primary key or unique constraint with UPSERT logic).
As a result, the system does not track repeated rediscovery events. Only the first detection timestamp is stored.
article_detected_utc_iso
Type: timestamptz


Nullable: No


Meaning: Timestamp (UTC) when the article URL was first discovered by the pipeline.


Behavior:


Set when the row is first inserted.


Not updated on subsequent rediscovery attempts.


If the same article appears again in future scans, the row is not duplicated and article_detected_utc_iso remains unchanged.



Row lifecycle fields
created_at (timestamptz, not null, default = now())
 When the row was inserted into the table (database insert timestamp).


updated_at (timestamptz, not null, default = now())
 When the row was last updated (e.g., title backfilled, published_utc_iso parsed later, URL canonicalization adjustments, scrape status fields updated, etc.).
 Maintained via database trigger (on update set updated_at = now()) or explicitly in pipeline code.



Notes and design choices
Why keep discovery separate from scraping?
This table’s job is to store what to scrape, not the scraped content.
Scrape outputs (page text, extraction status, content hash, etc.) are better placed in a separate scraped_articles table so:
the discovery ledger stays stable and compact,


scraping can be retried independently,


article updates can be represented as new scrape entries if needed later.


Cross-source duplicates
Because article_uuid is computed from the canonical final URL, the same article discovered from multiple sources maps to the same ID.
If you later need to track all sources that referenced the same article, a join table can be added (e.g., article_source_mentions) without changing the core identity model.

Example row (illustrative)
article_uuid: A_7f3c2a9f6c1b8d02


source_uuid: W_RSS_1


url_scraping_method: RSS


source_url: https://blog.cloudflare.com/rss/


article_title: Introducing Markdown for Agents


article_url_original:
 https://blog.cloudflare.com/markdown-for-agents/?utm_source=rss&utm_medium=rss


article_url_final:
 https://blog.cloudflare.com/markdown-for-agents/


url_original_to_final_match: FALSE


url_notes:
 resolved_redirects,removed_tracking_params,normalized_trailing_slash


published_utc_iso:
 2026-02-12T14:03:12+00:00


article_detected_utc_iso:
 2026-02-13T09:02:10+00:00


created_at:
 2026-02-13T09:02:10+00:00


updated_at:
 2026-02-13T09:02:10+00:00
