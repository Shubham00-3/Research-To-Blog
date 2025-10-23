"""Text chunking and semantic retrieval."""

import hashlib
import re
from typing import Any

import structlog

from app.data.models import Chunk, RetrievalResult, Source
from app.data.store import get_vector_store

logger = structlog.get_logger()


def chunk_text(
    text: str,
    chunk_size: int = 1500,
    overlap: int = 200,
) -> list[tuple[str, int, int]]:
    """
    Split text into overlapping chunks.

    Args:
        text: Text to chunk
        chunk_size: Target chunk size in characters
        overlap: Overlap between chunks in characters

    Returns:
        List of (chunk_text, start_char, end_char) tuples
    """
    if len(text) <= chunk_size:
        return [(text, 0, len(text))]

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence ending in the last 200 chars
            search_start = max(end - 200, start)
            sentence_match = None

            # Search for sentence boundaries (., !, ?) followed by space/newline
            for match in re.finditer(r'[.!?]\s+', text[search_start:end]):
                sentence_match = match

            if sentence_match:
                # Break at sentence boundary
                end = search_start + sentence_match.end()

        chunk = text[start:end].strip()
        if chunk:
            chunks.append((chunk, start, end))

        # Move start with overlap
        start = end - overlap if end < len(text) else len(text)

    return chunks


def create_chunks_from_source(source: Source) -> list[Chunk]:
    """
    Create chunks from a source document.

    Args:
        source: Source document

    Returns:
        List of Chunk objects
    """
    text_chunks = chunk_text(source.raw_content)

    chunks = []
    for i, (text, start, end) in enumerate(text_chunks):
        # Generate deterministic chunk ID
        chunk_id = hashlib.sha256(
            f"{source.source_id}:{start}:{end}".encode()
        ).hexdigest()[:24]

        # Build metadata, filtering out None values (ChromaDB doesn't accept None)
        metadata = {
            "url": source.url,
            "title": source.title,
            "domain": source.domain,
            "chunk_index": i,
        }
        
        # Add optional fields only if they have values
        if source.author:
            metadata["author"] = source.author
        if source.published_date:
            metadata["published_date"] = source.published_date
        
        chunk = Chunk(
            chunk_id=chunk_id,
            source_id=source.source_id,
            text=text,
            start_char=start,
            end_char=end,
            metadata=metadata,
        )
        chunks.append(chunk)

    logger.debug(
        "chunks_created",
        source_id=source.source_id,
        num_chunks=len(chunks),
        total_chars=len(source.raw_content),
    )

    return chunks


async def index_sources(sources: list[Source]) -> int:
    """
    Index sources in the vector store.

    Args:
        sources: List of sources to index

    Returns:
        Number of chunks created
    """
    vector_store = get_vector_store()

    all_chunks = []
    for source in sources:
        chunks = create_chunks_from_source(source)
        all_chunks.extend(chunks)

    # Add to vector store
    vector_store.add_chunks(all_chunks)

    logger.info(
        "sources_indexed",
        num_sources=len(sources),
        num_chunks=len(all_chunks),
    )

    return len(all_chunks)


async def retrieve_for_query(
    query: str,
    n_results: int = 10,
    source_filter: list[str] | None = None,
) -> list[RetrievalResult]:
    """
    Retrieve relevant chunks for a query.

    Args:
        query: Search query
        n_results: Number of results to return
        source_filter: Optional list of source IDs to filter by

    Returns:
        List of RetrievalResult objects
    """
    vector_store = get_vector_store()

    # Build metadata filter
    where = None
    if source_filter:
        where = {"source_id": {"$in": source_filter}}

    # Query vector store
    results = vector_store.query(
        query_text=query,
        n_results=n_results,
        where=where,
    )

    # Convert to RetrievalResult objects
    retrieval_results = [
        RetrievalResult(
            chunk_id=r["chunk_id"],
            source_id=r["metadata"].get("source_id", ""),
            text=r["text"],
            score=r["score"],
            metadata=r["metadata"],
        )
        for r in results
    ]

    logger.info(
        "retrieval_complete",
        query=query[:50],
        num_results=len(retrieval_results),
    )

    return retrieval_results


async def retrieve_for_claims(
    claims: list[str],
    n_results_per_claim: int = 5,
) -> dict[str, list[RetrievalResult]]:
    """
    Retrieve evidence for multiple claims.

    Args:
        claims: List of claim texts
        n_results_per_claim: Number of results per claim

    Returns:
        Dict mapping claim text to list of RetrievalResults
    """
    results = {}

    for claim in claims:
        claim_results = await retrieve_for_query(claim, n_results_per_claim)
        results[claim] = claim_results

    logger.info(
        "multi_claim_retrieval",
        num_claims=len(claims),
        total_results=sum(len(r) for r in results.values()),
    )

    return results

