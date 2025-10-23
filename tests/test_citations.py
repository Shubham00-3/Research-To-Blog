"""Tests for citation extraction and validation."""

import pytest

from app.data.models import Source
from app.tools.citation import (
    create_citation_map,
    extract_citation_markers,
    split_into_sentences,
    validate_citations,
)


def test_extract_citation_markers():
    """Test citation marker extraction."""
    text = "This is a fact [1]. Another fact [2][3]. Combined [4, 5, 6]."

    markers = extract_citation_markers(text)

    assert len(markers) == 4
    assert markers[0][1] == [1]
    assert markers[1][1] == [2]
    assert markers[2][1] == [3]
    assert markers[3][1] == [4, 5, 6]


def test_split_into_sentences():
    """Test sentence splitting."""
    text = "First sentence. Second sentence! Third sentence? Fourth."

    sentences = split_into_sentences(text)

    assert len(sentences) >= 4
    assert "First sentence" in sentences[0][0]
    assert "Second sentence" in sentences[1][0]


def test_create_citation_map(sample_sources: list[Source]):
    """Test citation map creation."""
    text = """
# Test Article

This is an introduction with a citation [1].

## Section 1

LLMs can detect bugs with high accuracy [1][2]. This helps developers [2].

Common knowledge doesn't need citation [COMMON].

## Section 2

More content with citations [3]. Final sentence [1][2][3].
""".strip()

    citation_map = create_citation_map(text, sample_sources)

    # Check bibliography
    assert len(citation_map.bibliography) == 3
    assert citation_map.bibliography[0].citation_id == 1
    assert citation_map.bibliography[0].source_id == "test_src_001"

    # Check sentence mappings
    assert len(citation_map.sentence_mappings) > 0

    # Check coverage (should be high with citations)
    assert citation_map.coverage_rate >= 0.7


def test_validate_citations_valid(sample_sources: list[Source]):
    """Test citation validation with valid citations."""
    text = "Fact with citation [1]. Another fact [2]."

    citation_map = create_citation_map(text, sample_sources)
    issues = validate_citations(citation_map)

    # Should have minimal issues (maybe uncited sentences)
    assert len(issues) <= 2


def test_validate_citations_invalid(sample_sources: list[Source]):
    """Test citation validation with invalid citations."""
    text = "Fact with valid citation [1]. Invalid citation [99]."

    citation_map = create_citation_map(text, sample_sources)
    issues = validate_citations(citation_map)

    # Should detect invalid citation ID
    assert any("Invalid citation ID [99]" in issue for issue in issues)


def test_no_uncited_claims_enforcement(sample_sources: list[Source]):
    """Test that uncited sentences are detected."""
    text = """
This sentence has a citation [1].
This sentence has no citation and is not common knowledge.
This is common knowledge [COMMON].
""".strip()

    citation_map = create_citation_map(text, sample_sources)
    issues = validate_citations(citation_map)

    # Should detect 1 uncited sentence
    assert any("lack citations" in issue for issue in issues)

