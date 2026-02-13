from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal


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
    created_at: datetime = Field(
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


class ArticleClassification(BaseModel):
    active_campaign: Literal["True", "False", "Not Sure"] = Field(
        description="Indicates if the article is classified as an 'Active Cyber Attack Campaign'"
    )
    cve: Literal["True", "False", "Not Sure"] = Field(
        description="Indicates if the article is classified as 'Common Vulnerabilities and Exposures (CVE)'"
    )
    digest: Literal["True", "False", "Not Sure"] = Field(
        description="Indicates if the article is classified as a 'Digest'"
    )


class ArticleCluster(BaseModel):
    campaign_name: str = Field(description="Name of the cluster/campaign")
    article_urls: list[str] = Field(
        default_factory=list,
        description="List of article URLs belonging to the cluster/campaign",
    )
    reasoning: str = Field(
        description="Brief explanation of why these articles were clustered together or where is only one url identified as part of the clusters"
    )


class ClusteringResult(BaseModel):
    clusters: list[ArticleCluster] = Field(
        default_factory=list, description="List of article clusters/campaigns"
    )
