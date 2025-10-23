"""Search tools with Tavily and DuckDuckGo fallback."""

import asyncio
from typing import Any

import structlog

from app.config import settings

logger = structlog.get_logger()


class SearchResult(dict):
    """Search result with url, title, content."""

    url: str
    title: str
    content: str
    score: float


async def search_tavily(query: str, max_results: int = 10) -> list[SearchResult]:
    """
    Search using Tavily API.

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        List of search results
    """
    try:
        from tavily import TavilyClient

        if not settings.tavily_api_key:
            logger.debug("tavily_api_key_not_set")
            return []

        client = TavilyClient(api_key=settings.tavily_api_key)

        # Run in thread pool since Tavily is sync
        response = await asyncio.to_thread(
            client.search,
            query=query,
            max_results=max_results,
            search_depth="advanced",
        )

        results = []
        for item in response.get("results", []):
            results.append(
                SearchResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    score=item.get("score", 0.0),
                )
            )

        logger.info("tavily_search_success", query=query, count=len(results))
        return results

    except ImportError:
        logger.warning("tavily_not_installed")
        return []
    except Exception as e:
        logger.warning("tavily_search_error", error=str(e))
        return []


async def search_duckduckgo(query: str, max_results: int = 10) -> list[SearchResult]:
    """
    Search using DuckDuckGo (free fallback).

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        List of search results
    """
    try:
        from duckduckgo_search import DDGS

        # Run in thread pool since DDGS is sync
        def _search():
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return results

        raw_results = await asyncio.to_thread(_search)

        results = []
        for item in raw_results:
            results.append(
                SearchResult(
                    url=item.get("href", item.get("link", "")),
                    title=item.get("title", ""),
                    content=item.get("body", item.get("snippet", "")),
                    score=0.5,  # DDG doesn't provide scores
                )
            )

        logger.info("duckduckgo_search_success", query=query, count=len(results))
        return results

    except ImportError:
        logger.error("duckduckgo_search_not_installed")
        return []
    except Exception as e:
        logger.warning("duckduckgo_search_error", error=str(e))
        return []


async def search(query: str, max_results: int = 30) -> list[SearchResult]:
    """
    Search for sources using available APIs.

    Tries Tavily first (if configured), falls back to DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum number of results to return

    Returns:
        List of search results
    """
    logger.info("search_started", query=query, max_results=max_results)

    # Try Tavily first
    if settings.tavily_api_key:
        results = await search_tavily(query, max_results)
        if results:
            return results

    # Fallback to DuckDuckGo
    logger.info("using_duckduckgo_fallback")
    results = await search_duckduckgo(query, max_results)

    return results


async def multi_query_search(
    queries: list[str], max_results_per_query: int = 15
) -> list[SearchResult]:
    """
    Execute multiple search queries in parallel and merge results.

    Args:
        queries: List of search queries
        max_results_per_query: Max results per query

    Returns:
        Deduplicated list of search results
    """
    logger.info("multi_query_search", num_queries=len(queries))

    # Execute searches in parallel
    tasks = [search(q, max_results_per_query) for q in queries]
    results_lists = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge and deduplicate
    seen_urls: set[str] = set()
    merged: list[SearchResult] = []

    for results in results_lists:
        if isinstance(results, Exception):
            logger.warning("search_error", error=str(results))
            continue

        for result in results:
            url = result["url"]
            if url and url not in seen_urls:
                seen_urls.add(url)
                merged.append(result)

    logger.info("multi_query_search_complete", total_results=len(merged))
    return merged

