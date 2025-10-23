"""LangGraph state definition for the pipeline."""

from datetime import datetime
from typing import Any, TypedDict

from app.data.models import (
    Article,
    DraftSection,
    GateDecision,
    Outline,
    QualityMetrics,
    RunMetrics,
    SEOMetadata,
    SourcePack,
    TopicSpec,
    Verdict,
)


class PipelineState(TypedDict, total=False):
    """
    Blackboard state for the research-to-blog pipeline.

    All state updates are immutable - agents return new state dicts
    that are merged with the existing state.
    """

    # Input
    run_id: str
    topic_spec: TopicSpec
    started_at: datetime

    # Planning phase
    outline: Outline

    # Sourcing phase
    source_pack: SourcePack

    # Indexing phase
    indexed_chunks: int

    # Summarization phase
    draft_sections: list[DraftSection]

    # Fact-checking phase
    verdicts: list[Verdict]

    # Writing phase
    article: Article

    # SEO phase
    seo_metadata: SEOMetadata

    # Quality gate
    gate_decision: GateDecision
    quality_metrics: QualityMetrics

    # Control flow
    retry_count: int
    should_retry: bool

    # Artifacts and logs
    artifacts: dict[str, Any]
    logs: list[str]

    # Metrics
    run_metrics: RunMetrics

    # Final status
    completed_at: datetime | None
    status: str  # "running", "completed", "failed"
    error: str | None


def create_initial_state(run_id: str, topic_spec: TopicSpec) -> PipelineState:
    """
    Create initial pipeline state.

    Args:
        run_id: Unique run identifier
        topic_spec: Topic specification

    Returns:
        Initial PipelineState
    """
    return PipelineState(
        run_id=run_id,
        topic_spec=topic_spec,
        started_at=datetime.utcnow(),
        retry_count=0,
        should_retry=False,
        artifacts={},
        logs=[],
        status="running",
        error=None,
    )

