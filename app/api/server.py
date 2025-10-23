"""FastAPI server for the research-to-blog pipeline."""

import uuid
from datetime import datetime
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import __version__
from app.config import settings
from app.data.models import TopicSpec
from app.exporters.markdown import export_json, export_markdown
from app.graph.state import create_initial_state, PipelineState
from app.graph.workflow import run_pipeline

# Configure structlog for JSON logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()

# FastAPI app
app = FastAPI(
    title="Research-to-Blog Pipeline API",
    description="Multi-agent pipeline for creating verified, well-cited articles from research topics",
    version=__version__,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for runs (in production, use Redis/DB)
runs_store: dict[str, PipelineState] = {}


# ============================================================================
# Request/Response Models
# ============================================================================


class RunRequest(BaseModel):
    """Request to run the pipeline."""

    topic: str = Field(..., description="Research topic or question")
    audience: str = Field(default="general", description="Target audience")
    goals: list[str] = Field(default_factory=list, description="Specific goals or angles")
    keywords: list[str] = Field(default_factory=list, description="Target keywords for SEO")
    constraints: dict[str, Any] = Field(default_factory=dict, description="Additional constraints")
    publish: bool = Field(default=False, description="Whether to publish to CMS")


class RunResponse(BaseModel):
    """Response from starting a run."""

    run_id: str
    status: str
    message: str
    started_at: datetime


class RunStatusResponse(BaseModel):
    """Response for run status check."""

    run_id: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: list[str] = Field(default_factory=list, description="Log entries")
    article: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    error: str | None = None


# ============================================================================
# Endpoints
# ============================================================================


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Research-to-Blog Pipeline API",
        "version": __version__,
        "docs": "/docs",
        "health": "/healthz",
    }


@app.get("/healthz")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "config": {
            "orch_model": settings.groq_model_orch,
            "writer_model": settings.groq_model_writer,
            "embed_backend": settings.embed_backend,
            "publish_target": settings.publish_target,
        },
    }


@app.post("/run", response_model=RunResponse)
async def create_run(request: RunRequest):
    """
    Start a new pipeline run.

    This endpoint starts the pipeline asynchronously and returns immediately
    with a run ID. Use GET /runs/{run_id} to check status.
    """
    logger.info("api_run_requested", topic=request.topic, audience=request.audience)

    # Generate run ID
    run_id = str(uuid.uuid4())[:8]

    # Create topic spec
    topic_spec = TopicSpec(
        topic=request.topic,
        audience=request.audience,
        goals=request.goals,
        keywords=request.keywords,
        constraints=request.constraints,
    )

    # Create initial state
    initial_state = create_initial_state(run_id, topic_spec)

    # Store initial state
    runs_store[run_id] = initial_state

    # Run pipeline in background
    # Note: In production, use background tasks or Celery
    import asyncio

    async def run_in_background():
        try:
            final_state = await run_pipeline(initial_state)
            runs_store[run_id] = final_state

            # Optionally publish
            if request.publish and final_state.get("status") == "completed":
                from app.exporters.cms import publish_article

                await publish_article(final_state)

        except Exception as e:
            logger.error("background_run_error", run_id=run_id, error=str(e))
            runs_store[run_id] = PipelineState(
                **initial_state,
                status="failed",
                error=str(e),
                completed_at=datetime.utcnow(),
            )

    # Schedule background task
    asyncio.create_task(run_in_background())

    return RunResponse(
        run_id=run_id,
        status="running",
        message=f"Pipeline started for topic: {request.topic}",
        started_at=initial_state["started_at"],
    )


@app.get("/runs/{run_id}", response_model=RunStatusResponse)
async def get_run_status(run_id: str):
    """
    Get the status of a pipeline run.

    Returns current status, progress logs, and results if completed.
    """
    if run_id not in runs_store:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    state = runs_store[run_id]

    # Build response
    response = RunStatusResponse(
        run_id=run_id,
        status=state.get("status", "unknown"),
        started_at=state.get("started_at"),
        completed_at=state.get("completed_at"),
        progress=state.get("logs", []),
        error=state.get("error"),
    )

    # Add article if completed
    if state.get("status") == "completed" and state.get("article"):
        article = state["article"]
        seo = state.get("seo_metadata")

        response.article = {
            "title": article.title,
            "content": article.content,
            "word_count": article.word_count,
            "reading_level": article.reading_level,
            "seo": {
                "title": seo.title if seo else article.title,
                "slug": seo.slug if seo else "",
                "meta_description": seo.meta_description if seo else "",
                "keywords": seo.keywords if seo else [],
            } if seo else None,
        }

    # Add metrics if available
    if state.get("quality_metrics"):
        metrics = state["quality_metrics"]
        response.metrics = {
            "citation_coverage": metrics.citation_coverage,
            "unsupported_claim_rate": metrics.unsupported_claim_rate,
            "avg_fact_confidence": metrics.avg_fact_confidence,
            "reading_level": metrics.reading_level,
            "total_claims": metrics.total_claims,
            "total_sources": metrics.total_sources,
        }

    return response


@app.get("/runs/{run_id}/markdown")
async def get_run_markdown(run_id: str):
    """
    Get the markdown export of a completed run.
    """
    if run_id not in runs_store:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    state = runs_store[run_id]

    if state.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Run not completed yet")

    if not state.get("article"):
        raise HTTPException(status_code=400, detail="No article in run")

    markdown = export_markdown(state)

    return {
        "run_id": run_id,
        "format": "markdown",
        "content": markdown,
    }


@app.get("/runs/{run_id}/json")
async def get_run_json(run_id: str):
    """
    Get the JSON export of a completed run.
    """
    if run_id not in runs_store:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    state = runs_store[run_id]

    if state.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Run not completed yet")

    return export_json(state)


@app.delete("/runs/{run_id}")
async def delete_run(run_id: str):
    """
    Delete a run from memory.
    """
    if run_id not in runs_store:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    del runs_store[run_id]

    return {"message": f"Run {run_id} deleted"}


@app.get("/runs")
async def list_runs():
    """
    List all runs in memory.
    """
    runs = []
    for run_id, state in runs_store.items():
        runs.append({
            "run_id": run_id,
            "status": state.get("status"),
            "topic": state.get("topic_spec", {}).get("topic") if state.get("topic_spec") else None,
            "started_at": state.get("started_at"),
            "completed_at": state.get("completed_at"),
        })

    return {"runs": runs, "count": len(runs)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

