"""Tests for quality gates and judge behavior."""

import pytest

from app.agents.judge import evaluate_quality, should_retry
from app.data.models import CitationMap, QualityMetrics, Verdict, VerdictType


@pytest.mark.asyncio
async def test_quality_gate_pass():
    """Test quality gate with passing metrics."""
    metrics = QualityMetrics(
        citation_coverage=0.98,
        unsupported_claim_rate=0.02,
        avg_fact_confidence=0.85,
        reading_level=65.0,
        total_claims=20,
        total_sources=5,
        total_citations=5,
    )

    verdicts = [
        Verdict(
            claim_id="c1",
            claim_text="Test claim",
            verdict=VerdictType.SUPPORTED,
            confidence=0.9,
            evidence=[],
            reasoning="Well supported",
        )
    ]

    decision = await evaluate_quality(metrics, verdicts, retry_count=0)

    assert decision.passed is True
    assert len(decision.failure_reasons) == 0


@pytest.mark.asyncio
async def test_quality_gate_fail_citation_coverage():
    """Test quality gate failure due to low citation coverage."""
    metrics = QualityMetrics(
        citation_coverage=0.70,  # Below threshold
        unsupported_claim_rate=0.02,
        avg_fact_confidence=0.85,
        reading_level=65.0,
        total_claims=20,
        total_sources=5,
        total_citations=5,
    )

    verdicts = []

    decision = await evaluate_quality(metrics, verdicts, retry_count=0)

    assert decision.passed is False
    assert any("Citation coverage" in reason for reason in decision.failure_reasons)
    assert len(decision.recommendations) > 0


@pytest.mark.asyncio
async def test_quality_gate_fail_unsupported_claims():
    """Test quality gate failure due to unsupported claims."""
    metrics = QualityMetrics(
        citation_coverage=0.98,
        unsupported_claim_rate=0.20,  # Too high
        avg_fact_confidence=0.85,
        reading_level=65.0,
        total_claims=20,
        total_sources=5,
        total_citations=5,
    )

    verdicts = [
        Verdict(
            claim_id="c1",
            claim_text="Unsupported claim",
            verdict=VerdictType.NEEDS_MORE_EVIDENCE,
            confidence=0.3,
            evidence=[],
            reasoning="Not enough evidence",
        )
    ]

    decision = await evaluate_quality(metrics, verdicts, retry_count=0)

    assert decision.passed is False
    assert any("Unsupported claim" in reason for reason in decision.failure_reasons)


@pytest.mark.asyncio
async def test_should_retry_logic():
    """Test retry decision logic."""
    from app.data.models import GateDecision

    # Create failing decision
    metrics = QualityMetrics(
        citation_coverage=0.80,
        unsupported_claim_rate=0.10,
        avg_fact_confidence=0.60,
        reading_level=65.0,
        total_claims=20,
        total_sources=5,
        total_citations=5,
    )

    decision = GateDecision(
        passed=False,
        gate_name="quality_gate",
        metrics=metrics,
        failure_reasons=["Citation coverage below threshold"],
        recommendations=["Add more citations"],
        retry_count=0,
    )

    # Should retry on first failure
    retry = await should_retry(decision, max_retries=2)
    assert retry is True

    # Should not retry after max retries
    decision.retry_count = 2
    retry = await should_retry(decision, max_retries=2)
    assert retry is False

