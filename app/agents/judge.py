"""Judge/Gatekeeper agent - enforces quality thresholds."""

import structlog

from app.config import settings
from app.data.models import GateDecision, QualityMetrics, Verdict
from app.tools.quality import check_quality_gates

logger = structlog.get_logger()


async def evaluate_quality(
    metrics: QualityMetrics,
    verdicts: list[Verdict],
    retry_count: int = 0,
) -> GateDecision:
    """
    Evaluate article quality against gates.

    Args:
        metrics: Quality metrics
        verdicts: List of fact-check verdicts
        retry_count: Number of previous retry attempts

    Returns:
        GateDecision with pass/fail and recommendations
    """
    logger.info(
        "judge_evaluating",
        citation_coverage=f"{metrics.citation_coverage:.2%}",
        unsupported_rate=f"{metrics.unsupported_claim_rate:.2%}",
        avg_confidence=f"{metrics.avg_fact_confidence:.2f}",
        retry_count=retry_count,
    )

    # Check quality gates
    passed, failures, recommendations = check_quality_gates(
        metrics=metrics,
        min_citation_coverage=settings.min_citation_coverage,
        max_unsupported_claims=settings.max_unsupported_claims,
        min_fact_confidence=settings.min_fact_confidence,
    )

    # Add specific recommendations based on verdict analysis
    if not passed:
        # Analyze which claims need work
        needs_evidence = [
            v for v in verdicts if v.verdict.value == "needs-more-evidence"
        ]

        if needs_evidence:
            recommendations.append(
                f"Find additional sources for {len(needs_evidence)} claims "
                "marked as 'needs-more-evidence'"
            )

        refuted = [v for v in verdicts if v.verdict.value == "refuted"]
        if refuted:
            recommendations.append(
                f"Remove or revise {len(refuted)} refuted claims"
            )

    # Create decision
    decision = GateDecision(
        passed=passed,
        gate_name="quality_gate",
        metrics=metrics,
        failure_reasons=failures,
        recommendations=recommendations,
        retry_count=retry_count,
    )

    if passed:
        logger.info("judge_passed", retry_count=retry_count)
    else:
        logger.warning(
            "judge_failed",
            num_failures=len(failures),
            num_recommendations=len(recommendations),
            retry_count=retry_count,
        )

    return decision


async def should_retry(decision: GateDecision, max_retries: int = 2) -> bool:
    """
    Determine if pipeline should retry based on gate decision.

    Args:
        decision: GateDecision from judge
        max_retries: Maximum allowed retries

    Returns:
        True if should retry, False otherwise
    """
    if decision.passed:
        return False

    if decision.retry_count >= max_retries:
        logger.warning(
            "max_retries_reached",
            retry_count=decision.retry_count,
            max_retries=max_retries,
        )
        return False

    # Only retry if failures are fixable
    fixable_issues = [
        "citation coverage",
        "unsupported claims",
        "fact confidence",
    ]

    is_fixable = any(
        any(issue in failure.lower() for issue in fixable_issues)
        for failure in decision.failure_reasons
    )

    if is_fixable:
        logger.info(
            "retry_recommended",
            retry_count=decision.retry_count,
            reasons=decision.failure_reasons,
        )
        return True

    return False

