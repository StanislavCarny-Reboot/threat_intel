"""FastAPI server for threat intelligence application."""

from typing import List, Optional
from datetime import datetime
import asyncio
import uuid
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from connectors.database import db
from models.entities import DataSources, RssParseRun
from loguru import logger

# Add rss_regex to path for imports
sys.path.insert(0, str(Path(__file__).parent / "rss_regex"))
try:
    from rss_regex.parse_rss_feeds import run as run_rss_parsing
except ImportError:
    logger.warning("Could not import parse_rss_feeds, RSS workflow endpoint will not work")
    run_rss_parsing = None

app = FastAPI(title="Threat Intelligence API")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DataSourceResponse(BaseModel):
    """Response model for datasource."""
    id: int
    name: str
    url: str
    active: str

    class Config:
        from_attributes = True


class UpdateDataSourceRequest(BaseModel):
    """Request model to update datasource active status."""
    active: str


class RunResponse(BaseModel):
    """Response model for RSS parse run."""
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    sources_processed: int
    items_extracted: int
    items_inserted: int
    error_message: Optional[str]

    class Config:
        from_attributes = True


@app.on_event("startup")
async def startup() -> None:
    """Connect to database on startup."""
    logger.info("Connecting to database...")
    await db.connect()
    logger.info("Database connected successfully")


@app.on_event("shutdown")
async def shutdown() -> None:
    """Disconnect from database on shutdown."""
    logger.info("Disconnecting from database...")
    await db.disconnect()
    logger.info("Database disconnected successfully")


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {"message": "Threat Intelligence API", "status": "running"}


@app.get("/api/datasources", response_model=List[DataSourceResponse])
async def get_datasources() -> List[DataSourceResponse]:
    """Get all datasources."""
    try:
        async with db.session() as session:
            result = await session.execute(select(DataSources))
            sources = result.scalars().all()
            return [
                DataSourceResponse(
                    id=source.id,
                    name=source.name,
                    url=source.url,
                    active=source.active
                )
                for source in sources
            ]
    except Exception as e:
        logger.error(f"Error fetching datasources: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch datasources")


@app.patch("/api/datasources/{datasource_id}", response_model=DataSourceResponse)
async def update_datasource_status(
    datasource_id: int,
    request: UpdateDataSourceRequest
) -> DataSourceResponse:
    """Update datasource active status."""
    try:
        async with db.session() as session:
            # Fetch the datasource
            result = await session.execute(
                select(DataSources).where(DataSources.id == datasource_id)
            )
            datasource = result.scalar_one_or_none()

            if not datasource:
                raise HTTPException(
                    status_code=404,
                    detail=f"Datasource with id {datasource_id} not found"
                )

            # Update active status
            datasource.active = request.active
            await session.commit()
            await session.refresh(datasource)

            logger.info(
                f"Updated datasource {datasource.name} (ID: {datasource_id}) "
                f"active status to: {request.active}"
            )

            return DataSourceResponse(
                id=datasource.id,
                name=datasource.name,
                url=datasource.url,
                active=datasource.active
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating datasource: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update datasource"
        )


@app.get("/api/health")
async def health_check() -> dict:
    """Health check endpoint."""
    is_healthy = await db.health_check()
    if is_healthy:
        return {"status": "healthy", "database": "connected"}
    else:
        raise HTTPException(status_code=503, detail="Database connection failed")


@app.get("/api/runs", response_model=List[RunResponse])
async def get_runs(limit: int = 10) -> List[RunResponse]:
    """Get RSS parse runs ordered by started_at descending."""
    try:
        async with db.session() as session:
            result = await session.execute(
                select(RssParseRun)
                .order_by(RssParseRun.started_at.desc())
                .limit(limit)
            )
            runs = result.scalars().all()
            return [
                RunResponse(
                    run_id=run.run_id,
                    started_at=run.started_at,
                    completed_at=run.completed_at,
                    status=run.status,
                    sources_processed=run.sources_processed,
                    items_extracted=run.items_extracted,
                    items_inserted=run.items_inserted,
                    error_message=run.error_message
                )
                for run in runs
            ]
    except Exception as e:
        logger.error(f"Error fetching runs: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch runs")


class TriggerRSSResponse(BaseModel):
    """Response model for triggering RSS workflow."""
    run_id: str
    message: str
    status: str


async def execute_rss_workflow(run_id: str) -> None:
    """Execute RSS parsing workflow in background with specified run_id."""
    try:
        logger.info(f"Starting RSS workflow execution with run_id: {run_id}")
        if run_rss_parsing is None:
            raise Exception("RSS parsing module not available")

        # The parse_rss_feeds.run() function now accepts run_id parameter
        # Pass disconnect_after=False to preserve the API's database connection
        await run_rss_parsing(run_id=run_id, disconnect_after=False)
        logger.info(f"RSS workflow completed for run_id: {run_id}")
    except Exception as e:
        logger.error(f"Error executing RSS workflow for run_id {run_id}: {e}")
        # The run() function already updates the record with error status


@app.post("/api/workflows/rss/trigger", response_model=TriggerRSSResponse)
async def trigger_rss_workflow(background_tasks: BackgroundTasks) -> TriggerRSSResponse:
    """Trigger RSS parsing workflow and return run_id immediately."""
    if run_rss_parsing is None:
        raise HTTPException(
            status_code=503,
            detail="RSS parsing module not available"
        )

    try:
        # Generate run_id that will be used by the workflow
        run_id = str(uuid.uuid4())
        logger.info(f"Triggering RSS workflow with run_id: {run_id}")

        # Create initial run record
        async with db.session() as session:
            run_record = RssParseRun(
                run_id=run_id,
                started_at=datetime.utcnow(),
                status="running"
            )
            session.add(run_record)
            await session.commit()

        # Execute workflow in background with the same run_id
        background_tasks.add_task(execute_rss_workflow, run_id)

        return TriggerRSSResponse(
            run_id=run_id,
            message="RSS workflow started",
            status="running"
        )
    except Exception as e:
        logger.error(f"Error triggering RSS workflow: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger RSS workflow: {str(e)}"
        )


@app.get("/api/runs/{run_id}", response_model=RunResponse)
async def get_run_details(run_id: str) -> RunResponse:
    """Get details for a specific run."""
    try:
        async with db.session() as session:
            result = await session.execute(
                select(RssParseRun).where(RssParseRun.run_id == run_id)
            )
            run = result.scalar_one_or_none()

            if not run:
                raise HTTPException(
                    status_code=404,
                    detail=f"Run with id {run_id} not found"
                )

            return RunResponse(
                run_id=run.run_id,
                started_at=run.started_at,
                completed_at=run.completed_at,
                status=run.status,
                sources_processed=run.sources_processed,
                items_extracted=run.items_extracted,
                items_inserted=run.items_inserted,
                error_message=run.error_message
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching run details: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch run details")
