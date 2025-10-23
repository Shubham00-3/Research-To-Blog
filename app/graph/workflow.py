"""LangGraph workflow orchestration."""

import asyncio
from datetime import datetime
from typing import Any

import structlog
from langgraph.graph import StateGraph, END

from app.agents.editor import edit_article
from app.agents.factchecker import verify_claims
from app.agents.judge import evaluate_quality, should_retry
from app.agents.planner import plan_article
from app.agents.seo import optimize_seo
from app.agents.sourcer import harvest_sources
from app.agents.summarizer import summarize_article
from app.agents.writer import write_article
from app.config import settings
from app.data.models import Claim, RunMetrics
from app.graph.state import PipelineState
from app.llm.clients import get_groq_client
from app.tools.quality import calculate_quality_metrics
from app.tools.retrieval import index_sources

logger = structlog.get_logger()


# ============================================================================
# Node Functions
# ============================================================================


async def plan_node(state: PipelineState) -> PipelineState:
    """Planning node - creates article outline."""
    logger.info("node_plan", run_id=state["run_id"])

    outline = await plan_article(state["topic_spec"])

    return PipelineState(
        outline=outline,
        logs=state.get("logs", []) + ["✓ Planning complete"],
    )


async def source_node(state: PipelineState) -> PipelineState:
    """Sourcing node - harvests and selects sources."""
    logger.info("node_source", run_id=state["run_id"])

    source_pack = await harvest_sources(state["outline"])

    return PipelineState(
        source_pack=source_pack,
        logs=state.get("logs", [])
        + [f"✓ Sourced {len(source_pack.sources)} documents"],
    )


async def index_node(state: PipelineState) -> PipelineState:
    """Indexing node - indexes sources in vector store."""
    logger.info("node_index", run_id=state["run_id"])

    sources = state["source_pack"].sources
    num_chunks = await index_sources(sources)

    return PipelineState(
        indexed_chunks=num_chunks,
        logs=state.get("logs", []) + [f"✓ Indexed {num_chunks} chunks"],
    )


async def summarize_node(state: PipelineState) -> PipelineState:
    """Summarization node - drafts content for each section."""
    logger.info("node_summarize", run_id=state["run_id"])

    drafts = await summarize_article(
        outline=state["outline"],
        sources=state["source_pack"].sources,
    )

    return PipelineState(
        draft_sections=drafts,
        logs=state.get("logs", [])
        + [f"✓ Drafted {len(drafts)} sections"],
    )


async def factcheck_node(state: PipelineState) -> PipelineState:
    """Fact-checking node - verifies claims."""
    logger.info("node_factcheck", run_id=state["run_id"])

    # Collect all claims from drafts
    all_claims: list[Claim] = []
    for draft in state.get("draft_sections", []):
        all_claims.extend(draft.claims)

    # Verify claims
    verdicts = await verify_claims(all_claims)

    return PipelineState(
        verdicts=verdicts,
        logs=state.get("logs", [])
        + [f"✓ Verified {len(verdicts)} claims"],
    )


async def write_node(state: PipelineState) -> PipelineState:
    """Writing node - composes article with citations."""
    logger.info("node_write", run_id=state["run_id"])

    article = await write_article(
        outline=state["outline"],
        drafts=state["draft_sections"],
        sources=state["source_pack"].sources,
        verdicts=state["verdicts"],
    )

    return PipelineState(
        article=article,
        logs=state.get("logs", [])
        + [f"✓ Article written ({article.word_count} words)"],
    )


async def edit_node(state: PipelineState) -> PipelineState:
    """Editing node - refines article for style."""
    logger.info("node_edit", run_id=state["run_id"])

    edited_article = await edit_article(
        article=state["article"],
        target_reading_level=settings.target_reading_level,
    )

    return PipelineState(
        article=edited_article,
        logs=state.get("logs", []) + ["✓ Article edited and refined"],
    )


async def seo_node(state: PipelineState) -> PipelineState:
    """SEO node - generates SEO metadata."""
    logger.info("node_seo", run_id=state["run_id"])

    seo_metadata = await optimize_seo(state["article"])

    return PipelineState(
        seo_metadata=seo_metadata,
        logs=state.get("logs", []) + ["✓ SEO metadata generated"],
    )


async def judge_node(state: PipelineState) -> PipelineState:
    """Judge node - evaluates quality gates."""
    logger.info("node_judge", run_id=state["run_id"])

    # Calculate quality metrics
    metrics = calculate_quality_metrics(
        citation_map=state["article"].citations,
        verdicts=state["verdicts"],
        article_text=state["article"].content,
        sources_count=len(state["source_pack"].sources),
    )

    # Evaluate
    decision = await evaluate_quality(
        metrics=metrics,
        verdicts=state["verdicts"],
        retry_count=state.get("retry_count", 0),
    )

    # Check if should retry
    retry = await should_retry(decision, max_retries=2)

    return PipelineState(
        quality_metrics=metrics,
        gate_decision=decision,
        should_retry=retry,
        logs=state.get("logs", [])
        + [f"✓ Quality gate: {'PASSED' if decision.passed else 'FAILED'}"],
    )


async def finalize_node(state: PipelineState) -> PipelineState:
    """Finalization node - prepares final output."""
    logger.info("node_finalize", run_id=state["run_id"])

    # Get usage stats
    client = get_groq_client()
    usage = client.get_usage_stats()

    # Calculate elapsed time
    elapsed = (datetime.utcnow() - state["started_at"]).total_seconds()

    # Create run metrics
    run_metrics = RunMetrics(
        run_id=state["run_id"],
        quality=state["quality_metrics"],
        time_elapsed_seconds=elapsed,
        total_tokens=usage["total_tokens"],
        groq_calls=usage["total_calls"],
        started_at=state["started_at"],
        completed_at=datetime.utcnow(),
        status="completed" if state["gate_decision"].passed else "completed_with_warnings",
    )

    return PipelineState(
        run_metrics=run_metrics,
        completed_at=datetime.utcnow(),
        status="completed",
        logs=state.get("logs", []) + ["✓ Pipeline complete"],
    )


async def retry_node(state: PipelineState) -> PipelineState:
    """Retry node - attempts to improve failing article."""
    logger.info("node_retry", run_id=state["run_id"], retry_count=state.get("retry_count", 0))

    # Increment retry count
    new_retry_count = state.get("retry_count", 0) + 1

    # For now, retry by sourcing more documents
    # In production, could be more sophisticated based on failure reasons

    logger.info("retry_sourcing_more", retry_count=new_retry_count)

    # Get more sources
    additional_sources = await harvest_sources(
        outline=state["outline"],
        max_sources=5,  # Add 5 more sources
        max_search_results=20,
    )

    # Merge with existing sources
    all_sources = state["source_pack"].sources + additional_sources.sources

    # Update source pack
    updated_pack = state["source_pack"]
    updated_pack.sources = all_sources

    return PipelineState(
        source_pack=updated_pack,
        retry_count=new_retry_count,
        should_retry=False,
        logs=state.get("logs", [])
        + [f"↻ Retry {new_retry_count}: Added {len(additional_sources.sources)} more sources"],
    )


# ============================================================================
# Conditional Edges
# ============================================================================


def should_retry_check(state: PipelineState) -> str:
    """Check if pipeline should retry."""
    if state.get("should_retry", False):
        return "retry"
    return "finalize"


# ============================================================================
# Workflow Builder
# ============================================================================


def build_workflow() -> StateGraph:
    """
    Build the LangGraph workflow.

    Returns:
        StateGraph ready to compile
    """
    workflow = StateGraph(PipelineState)

    # Add nodes
    workflow.add_node("plan", plan_node)
    workflow.add_node("source", source_node)
    workflow.add_node("index", index_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("factcheck", factcheck_node)
    workflow.add_node("write", write_node)
    workflow.add_node("edit", edit_node)
    workflow.add_node("seo", seo_node)
    workflow.add_node("judge", judge_node)
    workflow.add_node("retry", retry_node)
    workflow.add_node("finalize", finalize_node)

    # Add edges (linear flow with retry loop)
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "source")
    workflow.add_edge("source", "index")
    workflow.add_edge("index", "summarize")
    workflow.add_edge("summarize", "factcheck")
    workflow.add_edge("factcheck", "write")
    workflow.add_edge("write", "edit")
    workflow.add_edge("edit", "seo")
    workflow.add_edge("seo", "judge")

    # Conditional edge from judge
    workflow.add_conditional_edges(
        "judge",
        should_retry_check,
        {
            "retry": "retry",
            "finalize": "finalize",
        },
    )

    # Retry loops back to index
    workflow.add_edge("retry", "index")

    # End
    workflow.add_edge("finalize", END)

    return workflow


async def run_pipeline(state: PipelineState) -> PipelineState:
    """
    Run the complete pipeline.

    Args:
        state: Initial pipeline state

    Returns:
        Final pipeline state
    """
    logger.info("pipeline_started", run_id=state["run_id"])

    try:
        # Build and compile workflow
        workflow = build_workflow()
        app = workflow.compile()

        # Run with timeout
        timeout = settings.max_pipeline_time_seconds

        async def execute():
            result = await app.ainvoke(state)
            return result

        final_state = await asyncio.wait_for(execute(), timeout=timeout)

        logger.info(
            "pipeline_completed",
            run_id=state["run_id"],
            status=final_state.get("status"),
        )

        return final_state

    except asyncio.TimeoutError:
        logger.error("pipeline_timeout", run_id=state["run_id"])
        # Create a copy of state and update fields to avoid duplicate keyword args
        final_state = dict(state)
        final_state["status"] = "failed"
        final_state["error"] = f"Pipeline exceeded timeout of {timeout} seconds"
        final_state["completed_at"] = datetime.utcnow()
        return PipelineState(**final_state)

    except Exception as e:
        logger.error("pipeline_error", run_id=state["run_id"], error=str(e))
        # Create a copy of state and update fields to avoid duplicate keyword args
        final_state = dict(state)
        final_state["status"] = "failed"
        final_state["error"] = str(e)
        final_state["completed_at"] = datetime.utcnow()
        return PipelineState(**final_state)

