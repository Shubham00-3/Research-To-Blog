"""Source Harvester agent - finds and selects best sources."""

import structlog

from app.data.models import Outline, Source, SourcePack
from app.tools.scrape import deduplicate_sources, scrape_urls
from app.tools.search import multi_query_search

logger = structlog.get_logger()


def calculate_authority_score(domain: str) -> float:
    """
    Calculate domain authority score.

    Args:
        domain: Domain name

    Returns:
        Authority score (0.0 to 1.0)
    """
    # Simple heuristic - can be enhanced with real domain authority data
    high_authority = ['.edu', '.gov', '.ac.', 'nature.com', 'science.org', 'ieee.org']
    medium_authority = ['.org', 'medium.com', 'wikipedia.org']

    domain_lower = domain.lower()

    if any(auth in domain_lower for auth in high_authority):
        return 1.0
    elif any(auth in domain_lower for auth in medium_authority):
        return 0.7
    else:
        return 0.5


def calculate_relevance_score(source: Source, outline: Outline) -> float:
    """
    Calculate relevance score based on keyword matching.

    Args:
        source: Source document
        outline: Article outline

    Returns:
        Relevance score (0.0 to 1.0)
    """
    # Combine all keywords from outline
    keywords = set(outline.target_keywords)

    # Add section titles as keywords
    for section in outline.sections:
        keywords.add(section.title.lower())

    # Check how many keywords appear in source
    content_lower = source.raw_content.lower()
    title_lower = source.title.lower()

    matches = 0
    for keyword in keywords:
        if keyword.lower() in content_lower or keyword.lower() in title_lower:
            matches += 1

    # Normalize
    if not keywords:
        return 0.5

    return min(matches / len(keywords), 1.0)


def rank_sources(sources: list[Source], outline: Outline) -> list[Source]:
    """
    Rank sources by relevance and authority.

    Args:
        sources: List of sources to rank
        outline: Article outline

    Returns:
        Sorted list of sources
    """
    for source in sources:
        # Calculate scores
        authority = calculate_authority_score(source.domain)
        relevance = calculate_relevance_score(source, outline)

        # Combined score (60% relevance, 40% authority)
        source.relevance_score = relevance
        source.authority_score = authority

    # Sort by combined score
    sources.sort(
        key=lambda s: (0.6 * s.relevance_score + 0.4 * s.authority_score),
        reverse=True,
    )

    return sources


async def harvest_sources(
    outline: Outline,
    max_sources: int = 12,
    max_search_results: int = 30,
) -> SourcePack:
    """
    Harvest and select the best sources for an article.

    Args:
        outline: Article outline
        max_sources: Maximum number of sources to select
        max_search_results: Maximum search results to retrieve

    Returns:
        SourcePack with selected sources
    """
    logger.info("sourcer_started", max_sources=max_sources)

    # Build search queries from outline
    queries = [outline.title]

    # Add section-specific queries
    for section in outline.sections:
        queries.append(section.title)

    # Add keyword queries
    if outline.target_keywords:
        queries.extend(outline.target_keywords[:3])  # Top 3 keywords

    logger.info("search_queries_generated", num_queries=len(queries))

    # Search for sources
    search_results = await multi_query_search(
        queries=queries,
        max_results_per_query=max_search_results // len(queries),
    )

    logger.info("search_complete", total_results=len(search_results))

    # Extract URLs
    urls = [r["url"] for r in search_results[:max_search_results]]

    # Scrape URLs
    sources = await scrape_urls(urls, max_concurrent=5)

    # Deduplicate
    sources = deduplicate_sources(sources)

    logger.info("scraping_complete", total_sources=len(sources))

    # Rank sources
    sources = rank_sources(sources, outline)

    # Select top N
    selected_sources = sources[:max_sources]

    # Calculate diversity score (unique domains)
    unique_domains = len(set(s.domain for s in selected_sources))
    diversity_score = unique_domains / len(selected_sources) if selected_sources else 0.0

    # Generate rationale
    rationale = f"""
Selected {len(selected_sources)} sources from {len(sources)} candidates.
Criteria:
- Relevance to outline topics and keywords
- Domain authority (preferred .edu, .gov, established publications)
- Content diversity (covering different aspects)
- Recency and accessibility

Diversity: {unique_domains} unique domains out of {len(selected_sources)} sources.

Top sources:
{chr(10).join(f"- {s.title} ({s.domain}) - relevance: {s.relevance_score:.2f}, authority: {s.authority_score:.2f}" 
             for s in selected_sources[:5])}
""".strip()

    source_pack = SourcePack(
        sources=selected_sources,
        selection_rationale=rationale,
        total_candidates=len(sources),
        diversity_score=diversity_score,
    )

    logger.info(
        "sourcer_complete",
        selected=len(selected_sources),
        candidates=len(sources),
        diversity=f"{diversity_score:.2f}",
    )

    return source_pack

