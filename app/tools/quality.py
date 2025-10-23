"""Quality metrics and evaluation tools."""

import re

import structlog
import textstat

from app.data.models import CitationMap, QualityMetrics, Verdict, VerdictType

logger = structlog.get_logger()


def calculate_citation_coverage(citation_map: CitationMap) -> float:
    """
    Calculate the percentage of sentences that have citations.

    Args:
        citation_map: CitationMap object

    Returns:
        Coverage rate (0.0 to 1.0)
    """
    return citation_map.coverage_rate


def calculate_unsupported_claim_rate(verdicts: list[Verdict]) -> float:
    """
    Calculate the rate of unsupported or refuted claims.

    Args:
        verdicts: List of Verdict objects

    Returns:
        Unsupported rate (0.0 to 1.0)
    """
    if not verdicts:
        return 0.0

    unsupported_count = sum(
        1 for v in verdicts
        if v.verdict in (VerdictType.REFUTED, VerdictType.NEEDS_MORE_EVIDENCE)
    )

    return unsupported_count / len(verdicts)


def calculate_average_confidence(verdicts: list[Verdict]) -> float:
    """
    Calculate average fact-check confidence.

    Args:
        verdicts: List of Verdict objects

    Returns:
        Average confidence (0.0 to 1.0)
    """
    if not verdicts:
        return 0.0

    total_confidence = sum(v.confidence for v in verdicts)
    return total_confidence / len(verdicts)


def calculate_reading_level(text: str) -> float:
    """
    Calculate Flesch Reading Ease score.

    Scores:
    - 90-100: Very easy (5th grade)
    - 80-90: Easy (6th grade)
    - 70-80: Fairly easy (7th grade)
    - 60-70: Standard (8th-9th grade)
    - 50-60: Fairly difficult (10th-12th grade)
    - 30-50: Difficult (college)
    - 0-30: Very difficult (college graduate)

    Args:
        text: Article text

    Returns:
        Flesch reading ease score
    """
    # Remove citation markers for cleaner analysis
    clean_text = re.sub(r'\[\d+(?:\s*,\s*\d+)*\]', '', text)

    try:
        score = textstat.flesch_reading_ease(clean_text)
        return score
    except Exception as e:
        logger.warning("reading_level_calculation_error", error=str(e))
        return 60.0  # Default to "standard"


def count_words(text: str) -> int:
    """
    Count words in text.

    Args:
        text: Text to count

    Returns:
        Word count
    """
    # Remove citation markers
    clean_text = re.sub(r'\[\d+(?:\s*,\s*\d+)*\]', '', text)
    words = clean_text.split()
    return len(words)


def calculate_quality_metrics(
    citation_map: CitationMap,
    verdicts: list[Verdict],
    article_text: str,
    sources_count: int,
) -> QualityMetrics:
    """
    Calculate comprehensive quality metrics.

    Args:
        citation_map: Citation mapping
        verdicts: List of fact-check verdicts
        article_text: Full article text
        sources_count: Number of sources used

    Returns:
        QualityMetrics object
    """
    citation_coverage = calculate_citation_coverage(citation_map)
    unsupported_rate = calculate_unsupported_claim_rate(verdicts)
    avg_confidence = calculate_average_confidence(verdicts)
    reading_level = calculate_reading_level(article_text)

    metrics = QualityMetrics(
        citation_coverage=citation_coverage,
        unsupported_claim_rate=unsupported_rate,
        avg_fact_confidence=avg_confidence,
        reading_level=reading_level,
        total_claims=len(verdicts),
        total_sources=sources_count,
        total_citations=len(citation_map.bibliography),
    )

    logger.info(
        "quality_metrics_calculated",
        citation_coverage=f"{citation_coverage:.2%}",
        unsupported_rate=f"{unsupported_rate:.2%}",
        avg_confidence=f"{avg_confidence:.2f}",
        reading_level=f"{reading_level:.1f}",
    )

    return metrics


def check_quality_gates(
    metrics: QualityMetrics,
    min_citation_coverage: float = 0.95,
    max_unsupported_claims: float = 0.05,
    min_fact_confidence: float = 0.7,
) -> tuple[bool, list[str], list[str]]:
    """
    Check if quality metrics meet gate thresholds.

    Args:
        metrics: QualityMetrics object
        min_citation_coverage: Minimum required citation coverage
        max_unsupported_claims: Maximum allowed unsupported claim rate
        min_fact_confidence: Minimum required average confidence

    Returns:
        Tuple of (passed, failure_reasons, recommendations)
    """
    passed = True
    failures = []
    recommendations = []

    # Check citation coverage
    if metrics.citation_coverage < min_citation_coverage:
        passed = False
        failures.append(
            f"Citation coverage {metrics.citation_coverage:.1%} "
            f"below threshold {min_citation_coverage:.1%}"
        )
        recommendations.append(
            "Add citations to uncited sentences or mark them as common knowledge"
        )

    # Check unsupported claims
    if metrics.unsupported_claim_rate > max_unsupported_claims:
        passed = False
        failures.append(
            f"Unsupported claim rate {metrics.unsupported_claim_rate:.1%} "
            f"exceeds threshold {max_unsupported_claims:.1%}"
        )
        recommendations.append(
            "Find additional sources for unsupported claims or remove them"
        )

    # Check fact confidence
    if metrics.avg_fact_confidence < min_fact_confidence:
        passed = False
        failures.append(
            f"Average fact confidence {metrics.avg_fact_confidence:.2f} "
            f"below threshold {min_fact_confidence:.2f}"
        )
        recommendations.append(
            "Strengthen claims with better evidence or use more authoritative sources"
        )

    # Reading level warning (not a failure, just a recommendation)
    if metrics.reading_level < 50:
        recommendations.append(
            f"Reading level ({metrics.reading_level:.0f}) is difficult; "
            "consider simplifying language for broader audience"
        )
    elif metrics.reading_level > 80:
        recommendations.append(
            f"Reading level ({metrics.reading_level:.0f}) may be too simple; "
            "consider adding more sophisticated language if appropriate for audience"
        )

    logger.info(
        "quality_gates_checked",
        passed=passed,
        num_failures=len(failures),
        num_recommendations=len(recommendations),
    )

    return passed, failures, recommendations

