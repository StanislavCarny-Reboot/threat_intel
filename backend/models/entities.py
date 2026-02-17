from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    BigInteger,
    Date,
    Boolean,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from connectors import Base


class DataSources(Base):
    __tablename__ = "data_sources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    url = Column(String, unique=True, nullable=False)
    active = Column(String, default="true")


class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    cleaned_text = Column(Text, nullable=True)
    url = Column(String, unique=True, nullable=False)
    http_status_code = Column(Integer, nullable=True)
    published_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class RssItem(Base):
    __tablename__ = "rss_items"
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String, nullable=False)
    title = Column(Text, nullable=False)
    url = Column(String, unique=True, nullable=False)
    status = Column(String)
    http_status_code = Column(Integer, nullable=True)
    fetch_error = Column(Text, nullable=True)
    fetched_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    run_id = Column(String, nullable=True, index=True)


class ArticleClassificationLabel(Base):
    __tablename__ = "article_classification_labels"
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, nullable=False)
    url = Column(String, nullable=False)
    active_campaign = Column(String, nullable=False)
    cve = Column(String, nullable=False)
    digest = Column(String, nullable=False)
    label_source = Column(String, default="manual")  # 'manual', 'llm', 'evaluation'
    created_at = Column(DateTime, default=datetime.utcnow)


class RssParseRun(Base):
    __tablename__ = "rss_parse_runs"
    run_id = Column(String, primary_key=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="running")
    sources_processed = Column(Integer, default=0)
    items_extracted = Column(Integer, default=0)
    items_inserted = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SourcesMasterList(Base):
    __tablename__ = "sources_master_list"
    source_number = Column(BigInteger, nullable=True)
    source_uuid = Column(Text, primary_key=True, nullable=False)
    created_at = Column(Date, nullable=True)
    updated_at = Column(Date, nullable=True)
    source = Column(Text, nullable=True)
    url_scraping_method = Column(Text, nullable=True)
    source_name = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    status = Column(Text, nullable=True)
    status_code = Column(Text, nullable=True)
    last_ok_status_utc_iso = Column(TIMESTAMP(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=True)


class ExtractedArticleUrl(Base):
    __tablename__ = "extracted_article_urls_stano"
    article_uuid = Column(Text, primary_key=True, nullable=False)
    source_uuid = Column(Text, nullable=False)
    url_scraping_method = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    article_title = Column(Text, nullable=True)
    article_url_original = Column(Text, nullable=True)
    article_url_final = Column(Text, nullable=True)
    url_original_to_final_match = Column(Boolean, nullable=True)
    url_notes = Column(Text, nullable=True)
    published_utc_iso = Column(TIMESTAMP(timezone=True), nullable=True)
    article_detected_utc_iso = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=True)


class SourceErrorLog(Base):
    __tablename__ = "source_error_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_uuid = Column(Text, nullable=False, index=True)
    source_url = Column(Text, nullable=False)
    status_code = Column(Text, nullable=False)
    error_message = Column(Text, nullable=True)
    detected_at = Column(TIMESTAMP(timezone=True), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
