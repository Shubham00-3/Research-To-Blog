"""End-to-end smoke test for the pipeline."""

import uuid

import pytest

from app.data.models import TopicSpec
from app.graph.state import create_initial_state
from app.graph.workflow import run_pipeline


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pipeline_smoke(sample_topic_spec: TopicSpec):
    """
    Smoke test: run the complete pipeline with a real topic.

    This test requires:
    - GROQ_API_KEY in environment
    - Internet connection for search/scrape

    Mark as integration test (skip by default).
    """
    run_id = str(uuid.uuid4())[:8]

    # Create initial state
    initial_state = create_initial_state(run_id, sample_topic_spec)

    # Run pipeline
    final_state = await run_pipeline(initial_state)

    # Assertions
    assert final_state["status"] in ("completed", "completed_with_warnings")
    assert "article" in final_state
    assert final_state["article"].word_count > 500

    # Check quality metrics
    assert "quality_metrics" in final_state
    metrics = final_state["quality_metrics"]
    assert metrics.citation_coverage >= 0.8  # At least 80% coverage
    assert metrics.total_sources >= 3

    # Check citations
    assert len(final_state["article"].citations.bibliography) >= 3
    assert final_state["article"].citations.coverage_rate >= 0.8

