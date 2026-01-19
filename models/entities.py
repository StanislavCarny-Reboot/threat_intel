from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime
from connectors import Base


class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    url = Column(String, unique=True, nullable=False)
    published_at = Column(DateTime, default=datetime.utcnow)


class RssItem(Base):
    __tablename__ = "rss_items"
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String, nullable=False)
    title = Column(Text, nullable=False)
    url = Column(String, unique=True, nullable=False)
    status = Column(String)
    published_at = Column(DateTime, default=datetime.utcnow)
