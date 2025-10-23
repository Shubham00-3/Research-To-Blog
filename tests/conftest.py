"""Pytest configuration and fixtures."""

import pytest

from app.data.models import Source, TopicSpec


@pytest.fixture
def sample_topic_spec() -> TopicSpec:
    """Sample topic specification for testing."""
    return TopicSpec(
        topic="How do large language models improve code review",
        audience="software engineers",
        goals=[
            "Explain LLM capabilities in code review",
            "Discuss benefits and limitations",
        ],
        keywords=["LLM", "code review", "AI", "software development"],
    )


@pytest.fixture
def sample_sources() -> list[Source]:
    """Sample sources for testing."""
    return [
        Source(
            source_id="test_src_001",
            url="https://example.com/article1",
            title="LLMs in Software Engineering: A Survey",
            author="Jane Researcher",
            published_date="2024-01-15",
            domain="example.com",
            content_hash="abc123",
            raw_content="""
Large language models (LLMs) have shown significant promise in code review tasks.
Studies indicate that LLMs can detect bugs with 85% accuracy.
They excel at identifying common patterns like null pointer exceptions and memory leaks.
However, they struggle with complex domain-specific logic.
LLMs also help with code style consistency and documentation quality checks.
            """.strip(),
            relevance_score=0.9,
            authority_score=0.8,
        ),
        Source(
            source_id="test_src_002",
            url="https://research.edu/paper2",
            title="Effectiveness of AI-Assisted Code Review",
            author="Dr. John Smith",
            published_date="2024-02-20",
            domain="research.edu",
            content_hash="def456",
            raw_content="""
Research on AI-assisted code review shows mixed results.
In controlled studies, LLMs reduced review time by 40% on average.
The primary benefit is catching simple bugs and style issues automatically.
Human reviewers can then focus on architectural and design concerns.
Trust and verification remain important challenges in adoption.
            """.strip(),
            relevance_score=0.85,
            authority_score=1.0,
        ),
        Source(
            source_id="test_src_003",
            url="https://techblog.com/llm-limits",
            title="Limitations of LLMs in Code Analysis",
            author="Tech Blogger",
            published_date="2024-03-10",
            domain="techblog.com",
            content_hash="ghi789",
            raw_content="""
While LLMs offer benefits, they have clear limitations.
They cannot understand business logic or requirements.
Security vulnerabilities requiring deep context are often missed.
LLMs may generate false positives, creating reviewer fatigue.
The technology works best as an assistive tool, not a replacement.
            """.strip(),
            relevance_score=0.75,
            authority_score=0.6,
        ),
    ]

