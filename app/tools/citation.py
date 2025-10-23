"""Citation extraction, validation, and mapping tools."""

import re
from typing import Any

import structlog

from app.data.models import Citation, CitationMap, SentenceCitation, Source

logger = structlog.get_logger()


def extract_citation_markers(text: str) -> list[tuple[int, list[int]]]:
    """
    Extract citation markers from text.

    Finds patterns like [1], [2][3], [1,2,3], etc.

    Args:
        text: Text with citation markers

    Returns:
        List of (position, citation_ids) tuples
    """
    markers = []

    # Pattern: [1], [2][3], [1,2,3], [1, 2, 3]
    pattern = r'\[(\d+(?:\s*,\s*\d+)*)\]'

    for match in re.finditer(pattern, text):
        position = match.start()
        citation_str = match.group(1)

        # Parse citation IDs
        ids = [int(num.strip()) for num in citation_str.split(',')]
        markers.append((position, ids))

    return markers


def split_into_sentences(text: str) -> list[tuple[str, int, int]]:
    """
    Split text into sentences with character positions.

    Args:
        text: Text to split

    Returns:
        List of (sentence, start_char, end_char) tuples
    """
    # Simple sentence splitter (can be improved with NLTK/spaCy)
    # Handles common cases: ., !, ? followed by space or end of text

    sentences = []
    pattern = r'([^.!?]+[.!?]+)'

    last_end = 0
    for match in re.finditer(pattern, text):
        sentence = match.group(0).strip()
        if sentence:
            start = text.index(sentence, last_end)
            end = start + len(sentence)
            sentences.append((sentence, start, end))
            last_end = end

    # Catch any remaining text
    if last_end < len(text):
        remaining = text[last_end:].strip()
        if remaining:
            sentences.append((remaining, last_end, len(text)))

    return sentences


def create_citation_map(
    text: str,
    sources: list[Source],
    common_knowledge_phrases: list[str] | None = None,
) -> CitationMap:
    """
    Create a complete citation map for text.

    Args:
        text: Article text with citation markers
        sources: List of source documents
        common_knowledge_phrases: Optional phrases to mark as common knowledge

    Returns:
        CitationMap object
    """
    common_knowledge_phrases = common_knowledge_phrases or []

    # Create bibliography from sources
    bibliography = []
    source_map = {}  # source_id -> citation_id

    for i, source in enumerate(sources, 1):
        citation = Citation(
            citation_id=i,
            source_id=source.source_id,
            title=source.title,
            author=source.author,
            published_date=source.published_date,
            url=source.url,
            accessed_date=source.fetch_timestamp.strftime("%Y-%m-%d"),
        )
        bibliography.append(citation)
        source_map[source.source_id] = i

    # Split into sentences
    sentences = split_into_sentences(text)

    # Map sentences to citations
    sentence_mappings = []
    cited_count = 0

    for sentence, start, end in sentences:
        # Extract citation markers in this sentence
        sentence_text_for_search = text[start:end]
        markers = extract_citation_markers(sentence_text_for_search)

        # Collect all citation IDs
        citation_ids = []
        for _, ids in markers:
            citation_ids.extend(ids)

        # Remove duplicates and sort
        citation_ids = sorted(set(citation_ids))

        # Check if common knowledge
        is_common = any(
            phrase.lower() in sentence.lower() for phrase in common_knowledge_phrases
        )

        # Also check for [COMMON] tag
        if '[COMMON]' in sentence:
            is_common = True
            sentence = sentence.replace('[COMMON]', '').strip()

        mapping = SentenceCitation(
            sentence=sentence,
            start_char=start,
            end_char=end,
            citation_ids=citation_ids,
            is_common_knowledge=is_common,
        )

        sentence_mappings.append(mapping)

        # Count cited sentences
        if citation_ids or is_common:
            cited_count += 1

    # Calculate coverage
    total_sentences = len(sentences)
    coverage_rate = cited_count / total_sentences if total_sentences > 0 else 0.0

    citation_map = CitationMap(
        bibliography=bibliography,
        sentence_mappings=sentence_mappings,
        coverage_rate=coverage_rate,
    )

    logger.info(
        "citation_map_created",
        total_sentences=total_sentences,
        cited_sentences=cited_count,
        coverage_rate=coverage_rate,
        num_sources=len(bibliography),
    )

    return citation_map


def validate_citations(citation_map: CitationMap) -> list[str]:
    """
    Validate citations and return list of issues.

    Checks:
    - All citation IDs reference valid bibliography entries
    - No dangling citations
    - Citation coverage meets threshold

    Args:
        citation_map: CitationMap to validate

    Returns:
        List of validation error messages
    """
    issues = []

    # Get valid citation IDs
    valid_ids = {c.citation_id for c in citation_map.bibliography}

    # Check each sentence
    for mapping in citation_map.sentence_mappings:
        for cit_id in mapping.citation_ids:
            if cit_id not in valid_ids:
                issues.append(
                    f"Invalid citation ID [{cit_id}] in sentence: {mapping.sentence[:50]}..."
                )

    # Check for uncited sentences (excluding common knowledge)
    uncited = [
        m for m in citation_map.sentence_mappings
        if not m.citation_ids and not m.is_common_knowledge
    ]

    if uncited:
        issues.append(
            f"{len(uncited)} sentences lack citations and are not marked as common knowledge"
        )

    logger.info(
        "citation_validation",
        total_issues=len(issues),
        uncited_count=len(uncited),
    )

    return issues


def format_bibliography_markdown(citations: list[Citation]) -> str:
    """
    Format bibliography as Markdown.

    Args:
        citations: List of Citation objects

    Returns:
        Formatted bibliography string
    """
    lines = ["## References\n"]

    for citation in sorted(citations, key=lambda c: c.citation_id):
        parts = [f"[{citation.citation_id}]"]

        if citation.author:
            parts.append(f"{citation.author}.")

        parts.append(f'"{citation.title}."')

        if citation.published_date:
            parts.append(f"Published {citation.published_date}.")

        parts.append(f"Available at: {citation.url}")

        if citation.accessed_date:
            parts.append(f"(accessed {citation.accessed_date})")

        lines.append(" ".join(parts))

    return "\n".join(lines)


def assign_citations_to_claims(
    claims: list[dict[str, Any]],
    sources: list[Source],
) -> list[dict[str, Any]]:
    """
    Assign citation IDs to claims based on their evidence.

    Args:
        claims: List of claim dicts with 'evidence' field
        sources: List of source documents

    Returns:
        Updated claims with 'citation_ids' field
    """
    # Build source_id -> citation_id map
    source_to_cit = {s.source_id: i + 1 for i, s in enumerate(sources)}

    for claim in claims:
        citation_ids = []

        # Extract citation IDs from evidence
        if 'evidence' in claim:
            for evidence in claim['evidence']:
                source_id = evidence.get('source_id')
                if source_id and source_id in source_to_cit:
                    cit_id = source_to_cit[source_id]
                    if cit_id not in citation_ids:
                        citation_ids.append(cit_id)

        claim['citation_ids'] = sorted(citation_ids)

    return claims

