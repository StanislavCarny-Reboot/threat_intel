# sources_master_list (Supabase/Postgres)

Table 1: sources_master_list
Purpose
sources_master_list is the master registry of all Threat Intelligence content sources the system monitors. At the current stage, it contains web sources that are accessed either via RSS/Atom feeds or by directly visiting a web page (non-RSS). Social media sources may be added later.
This table exists to support the first stage of the threat intelligence pipeline: discovering newly published articles (within the last ~25 hours) from a curated set of sources. The system also uses this table to track the operational health of each source (whether it was reachable, whether parsing succeeded, and why failures occurred).
How it is used in the pipeline
A recurring collection process runs roughly once every 24 hours.


For each active source, the process attempts to access the URL defined in source_url using the method defined in url_scraping_method.


If the source is successfully accessed and parsed, newly published items (published within the last 25 hours) are identified and stored in the next-stage table (e.g., extracted_article_urls).


The source record is updated with:


current status (status, status_code)


last_ok_status_utc_iso if the scrape succeeded


This table is therefore both:
a configuration registry (what to crawl, how to crawl it), and


a health/telemetry surface (what worked, what broke, when it last worked).



Primary Key
source_uuid
Type: text


Role: Primary key; stable unique identifier for the source.


Format: {SourceTypeAbbrev}_{ScrapeMethod}_{SequenceNumber}


Source type abbreviations:


W = Website


SM = Social Media (future)


Scraping method codes:


RSS = RSS/Atom feed access


DIR = Direct access to a webpage (HTML)


Sequence number: integer, assigned when sources are added within that category.


Examples:


W_RSS_1


W_DIR_12


Notes
This value is the canonical identifier referenced by downstream tables (e.g., extracted article URLs).


It should be unique and immutable once created (treat it as the stable key).



Columns and Definitions
Identification & lifecycle
source_number
Type: integer


Meaning: A human-friendly ordering number showing the order in which sources were added overall.


created_at
Type: date (YYYY-MM-DD)


Meaning: Date when the source was first added to the registry.


updated_at
Type: date (YYYY-MM-DD)


Meaning: Date when source metadata (e.g., name/URL/method) was last manually edited.




Source configuration
source
Type: text


Meaning: High-level type of content source.


Allowed values (current + planned):


Website (current)


Social Media (future)


url_scraping_method
Type: text


Meaning: How the system should access the source URL.


Allowed values:


RSS — source_url points to a feed endpoint (RSS/Atom)


Direct — source_url points to a webpage (HTML) that must be parsed directly


source_name
Type: text


Meaning: Human-readable name of the source (display label).


source_url
Type: text


Meaning: The URL that is visited during discovery.


For RSS: RSS/Atom feed URL


For DIR: webpage URL that lists or links to articles


is_active
Type: boolean


Default: true


Meaning: Whether the source should be included in automated daily discovery.


true: included


false: skipped (kept for history / potential reactivation)



Operational health & scrape telemetry
status
Type: text


Meaning: High-level outcome of the most recent access attempt.


Allowed values:


OK


ERROR


status_code
Type: text


Meaning: A structured, machine-friendly code describing the last scrape outcome. This is used for consistent monitoring and for branching logic in scrapers and retries.


Allowed values (recommended set):


OK


NO_RECENT_ARTICLES (not an error; access + parse succeeded but no items in last 25h, status is OK)


HTTP_401_UNAUTHORIZED


HTTP_403_FORBIDDEN


HTTP_404_NOT_FOUND


HTTP_408_TIMEOUT


HTTP_429_TOO_MANY_REQUESTS


HTTP_5XX_SERVER_ERROR


CONNECTION_TIMEOUT


CONNECTION_REFUSED


DNS_ERROR


SSL_ERROR


REDIRECT_LOOP


INVALID_CONTENT_TYPE


PARSING_ERROR (HTML/feed structure changed, selectors broken, etc.)


ROBOTS_BLOCKED (if you detect/decide to respect robots restrictions)


UNKNOWN_ERROR


Notes
When status = 'OK', status_code should be either OK or NO_RECENT_ARTICLES.


When status = 'ERROR', status_code must be one of the error codes above (or a future extension).



last_ok_status_utc_iso
Type: timestamptz


Meaning: Timestamp of the last time the system status was OK - successfully accessed and processed the source. If the status is ERROR, the time stamp is not updated.


Timezone handling:


Store as UTC (canonical)





