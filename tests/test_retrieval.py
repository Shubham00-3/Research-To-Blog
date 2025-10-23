"""Tests for retrieval and indexing."""

import pytest

from app.data.models import Source
from app.tools.retrieval import chunk_text, create_chunks_from_source, index_sources, retrieve_for_query


def test_chunk_text():
    """Test text chunking."""
    text = "Sentence one. " * 200  # Long text

    chunks = chunk_text(text, chunk_size=500, overlap=100)

    assert len(chunks) > 1
    assert all(len(chunk[0]) <= 600 for chunk in chunks)  # Allow some margin

    # Check overlap exists
    if len(chunks) > 1:
        # Last part of first chunk should appear in second chunk
        first_chunk_end = chunks[0][0][-50:]
        second_chunk_start = chunks[1][0][:150]
        assert any(word in second_chunk_start for word in first_chunk_end.split())


def test_create_chunks_from_source(sample_sources: list[Source]):
    """Test chunk creation from source."""
    source = sample_sources[0]

    chunks = create_chunks_from_source(source)

    assert len(chunks) >= 1
    assert all(chunk.source_id == source.source_id for chunk in chunks)
    assert all(chunk.chunk_id for chunk in chunks)
    assert all(chunk.text for chunk in chunks)


@pytest.mark.asyncio
async def test_index_and_retrieve(sample_sources: list[Source]):
    """Test indexing and retrieval."""
    # Index sources
    num_chunks = await index_sources(sample_sources)

    assert num_chunks >= len(sample_sources)

    # Retrieve
    results = await retrieve_for_query("LLMs detect bugs", n_results=5)

    assert len(results) > 0
    assert all(r.score >= 0 for r in results)
    assert all(r.text for r in results)

    # Results should be relevant
    top_result = results[0]
    assert "LLM" in top_result.text or "bug" in top_result.text or "code" in top_result.text

