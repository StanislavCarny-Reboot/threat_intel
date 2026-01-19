from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class LLMRssFeedItem(BaseModel):
    source_name: str = Field(
        description="Name of the source from which the article was obtained"
    )
    title: str = Field(description="Title of the article")
    url: str = Field(description="URL of the article")
    published_at: datetime = Field(
        description="Publication date and time of the article in format YYYY-MM-DD HH:MM:SS without timezone "
    )


class LLMRSSFeed(BaseModel):
    items: list["LLMRssFeedItem"] = Field(
        default_factory=list, description="List of articles from the RSS feed"
    )


class ThreatCampaign(BaseModel):
    id: str = Field(description="Unique identifier for the threat")
    title: str = Field(description="Title of the threat campaign")
    created_at: str = Field(
        description="Creation timestamp in format YYYY-MM-DD HH:MM:SS without timezone"
    )
    source_url: str = Field(
        description="Source URL where the threat information was obtained"
    )
    threat_summary: str = Field(
        description="Summary of the campaign, surfacing key behaviors, which companies are affected"
    )
    extracted_ioc: list[str] = Field(
        default_factory=list,
        description="Indicator of Compromise - e.g. Malicious File Hash, IP Address",
    )
    mitre_mapping: list[str] = Field(
        default_factory=list,
        description="MITRE ATT&CK techniques associated with the threat campaign",
    )
