"""Seed data_sources table with initial RSS feeds."""

import asyncio
from connectors.database import db
from models.entities import DataSources
from loguru import logger


DATA_SOURCES = [
    (1, "cybersecurity_news", "https://cybersecuritynews.com/feed/", "true"),
    (2, "Sans Technology Institute", "https://isc.sans.edu/rssfeed.xml", "true"),
    (3, "Bleeping Computer", "https://www.bleepingcomputer.com/feed/", "true"),
    (4, "The DFIR Report", "https://thedfirreport.com/feed/", "true"),
    (7, "Daily Dark Web", "https://dailydarkweb.net/feed/", "true"),
    (8, "Dark Reading", "https://www.darkreading.com/rss.xml", "true"),
    (9, "Sophos", "https://www.sophos.com/en-us/blog/feed", "true"),
    (10, "Talos Intelligence", "https://feeder.co/discover/2a2d096933/blog-talosintel-com", "true"),
    (11, "Horizon3", "https://horizon3.ai/feed/", "true"),
    (13, "Morphisec", "https://www.morphisec.com/feed/?post_type=blog", "true"),
    (14, "Checkpoint", "https://research.checkpoint.com/feed/", "true"),
    (15, "Infosecurity", "http://www.infosecurity-magazine.com/rss/news/", "true"),
    (16, "S-RM Inform", "https://www.s-rminform.com/latest-thinking/rss.xml", "true"),
    (17, "GB Hackers", "https://gbhackers.com/feed/", "true"),
    (18, "Recorded Future", "https://feeder.co/discover/d119631d06/recordedfuture-com", "true"),
    (19, "The Hacker News", "https://feeds.feedburner.com/TheHackersNews", "true"),
    (20, "SecurityOnline", "https://securityonline.info/feed/", "true"),
    (21, "ciosea.economictimes", "https://ciosea.economictimes.indiatimes.com/rss/security", "true"),
    (5, "Huntress", "https://www.huntress.com/blog/rss.xml", "false"),
    (12, "Cyware", "https://www.cyware.com/sitemap.xml", "false"),
]


async def main() -> None:
    """Insert or update data sources in database (upsert)."""
    try:
        logger.info("Connecting to database...")
        await db.connect()

        logger.info(f"Upserting {len(DATA_SOURCES)} data sources...")

        async with db.session() as session:
            from sqlalchemy import select

            for source_id, name, url, active in DATA_SOURCES:
                # Check if datasource already exists
                result = await session.execute(
                    select(DataSources).where(DataSources.id == source_id)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing record
                    existing.name = name
                    existing.url = url
                    existing.active = active
                    logger.debug(f"Updated: {name} (ID: {source_id})")
                else:
                    # Insert new record
                    data_source = DataSources(
                        id=source_id,
                        name=name,
                        url=url,
                        active=active,
                    )
                    session.add(data_source)
                    logger.debug(f"Inserted: {name} (ID: {source_id})")

            await session.commit()
            logger.info("All data sources upserted successfully!")

        # Verify final state
        async with db.session() as session:
            from sqlalchemy import select

            result = await session.execute(select(DataSources))
            sources = result.scalars().all()
            logger.info(f"Total data sources in database: {len(sources)}")

    except Exception as e:
        logger.error(f"Error seeding data sources: {e}")
        raise
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
