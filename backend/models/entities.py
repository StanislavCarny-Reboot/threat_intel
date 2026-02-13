from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime
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
