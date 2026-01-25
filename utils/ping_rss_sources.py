import asyncio
import requests
from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import select
from models.entities import DataSources
from connectors.database import db

load_dotenv()


async def ping_rss_source(source: DataSources) -> dict:
    """Ping a single RSS source and return response info."""
    try:
        response = await asyncio.to_thread(requests.get, source.url, timeout=10)

        try:
            result = {
                "name": source.name,
                "url": source.url,
                "status_code": response.status_code,
                "character_count": len(response.text) if response.text else 0,
                "content_type": response.headers.get("content-type", "unknown"),
                "success": response.status_code == 200,
            }

            if response.status_code == 200:
                logger.info(f"✅ {source.name}: {result['character_count']} characters")
            else:
                logger.warning(f"❌ {source.name}: HTTP {response.status_code}")

            return result
        finally:
            try:
                response.close()
            except Exception:
                pass

    except requests.exceptions.RequestException as e:
        result = {
            "name": source.name,
            "url": source.url,
            "status_code": None,
            "character_count": 0,
            "content_type": None,
            "success": False,
            "error": str(e),
        }
        logger.error(f"❌ {source.name}: {e}")
        return result


async def ping_all_sources():
    """Ping all active RSS sources and report results."""
    await db.connect()
    logger.info("Database connected successfully")

    # Load all active RSS sources
    async with db.session() as session:
        result = await session.execute(
            select(DataSources).where(DataSources.active == "true")
        )
        sources = result.scalars().all()

    if not sources:
        logger.error("No active data sources found in database")
        return

    logger.info(f"Testing {len(sources)} RSS sources...")

    # Ping all sources concurrently
    results = await asyncio.gather(*(ping_rss_source(src) for src in sources))

    # Summary statistics
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    logger.info(f"\n📊 SUMMARY:")
    logger.info(f"Total sources: {len(results)}")
    logger.info(
        f"Successful: {len(successful)} ({len(successful)/len(results)*100:.1f}%)"
    )
    logger.info(f"Failed: {len(failed)} ({len(failed)/len(results)*100:.1f}%)")

    if successful:
        total_chars = sum(r["character_count"] for r in successful)
        avg_chars = total_chars / len(successful)
        logger.info(f"Average response size: {avg_chars:,.0f} characters")

        # Top 5 largest responses
        largest = sorted(successful, key=lambda x: x["character_count"], reverse=True)
        logger.info(f"\n🏆 TOP 5 LARGEST RESPONSES:")
        for i, r in enumerate(largest, 1):
            logger.info(f"{i}. {r['name']}: {r['character_count']:,} chars")

    if failed:
        logger.info(f"\n❌ FAILED SOURCES:")
        for r in failed:
            error_msg = r.get("error", f"HTTP {r['status_code']}")
            logger.info(f"• {r['name']}: {error_msg}")

    return results


if __name__ == "__main__":
    asyncio.run(ping_all_sources())
