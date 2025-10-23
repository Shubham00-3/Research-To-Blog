"""Web scraping with robust error handling and content extraction."""

import asyncio
import hashlib
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog
from readability import Document
import trafilatura

from app.data.models import Source

logger = structlog.get_logger()


async def fetch_url(
    url: str,
    timeout: float = 30.0,
    max_retries: int = 2,
) -> tuple[str, dict[str, Any]]:
    """
    Fetch URL content with error handling.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts

    Returns:
        Tuple of (html_content, metadata)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0; +https://example.com/bot)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                # Check content type
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    raise ValueError(f"Unsupported content type: {content_type}")

                metadata = {
                    "status_code": response.status_code,
                    "content_type": content_type,
                    "final_url": str(response.url),
                    "encoding": response.encoding or "utf-8",
                }

                logger.info("fetch_success", url=url, status=response.status_code)
                return response.text, metadata

        except httpx.HTTPStatusError as e:
            logger.warning(
                "http_error",
                url=url,
                status=e.response.status_code,
                attempt=attempt + 1,
            )
            if e.response.status_code in (403, 404, 410):
                # Don't retry these
                raise
            if attempt < max_retries:
                await asyncio.sleep(2**attempt)
            else:
                raise

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning("fetch_timeout", url=url, attempt=attempt + 1)
            if attempt < max_retries:
                await asyncio.sleep(2**attempt)
            else:
                raise

        except Exception as e:
            logger.error("fetch_error", url=url, error=str(e))
            raise

    raise RuntimeError(f"Failed to fetch {url}")


def extract_content(html: str, url: str) -> dict[str, Any]:
    """
    Extract main content and metadata from HTML.

    Uses trafilatura for content extraction and readability as fallback.

    Args:
        html: HTML content
        url: Source URL

    Returns:
        Dict with extracted content and metadata
    """
    # Try trafilatura first (better for articles)
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
        output_format="txt",
        url=url,
    )

    # Extract metadata
    metadata = trafilatura.extract_metadata(html, default_url=url)

    if extracted and len(extracted.strip()) > 100:
        return {
            "content": extracted.strip(),
            "title": metadata.title if metadata else None,
            "author": metadata.author if metadata else None,
            "date": metadata.date if metadata else None,
            "method": "trafilatura",
        }

    # Fallback to readability
    logger.debug("using_readability_fallback", url=url)
    doc = Document(html)

    return {
        "content": doc.summary(html_partial=False),
        "title": doc.title(),
        "author": None,
        "date": None,
        "method": "readability",
    }


def get_canonical_url(url: str) -> str:
    """
    Get canonical URL (normalized).

    Args:
        url: Original URL

    Returns:
        Canonical URL
    """
    parsed = urlparse(url)

    # Remove common tracking parameters
    # For production, use a more comprehensive list
    canonical = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    # Remove trailing slash
    if canonical.endswith("/"):
        canonical = canonical[:-1]

    return canonical


async def scrape_url(url: str) -> Source | None:
    """
    Scrape a URL and return a Source object.

    Args:
        url: URL to scrape

    Returns:
        Source object or None if scraping failed
    """
    try:
        # Fetch HTML
        html, fetch_metadata = await fetch_url(url)

        # Extract content
        extracted = extract_content(html, url)

        # Get canonical URL
        canonical = get_canonical_url(fetch_metadata.get("final_url", url))

        # Generate content hash
        content_hash = hashlib.sha256(extracted["content"].encode()).hexdigest()

        # Generate deterministic source ID
        source_id = hashlib.sha256(canonical.encode()).hexdigest()[:16]

        # Parse domain
        domain = urlparse(canonical).netloc

        # Create Source object
        source = Source(
            source_id=source_id,
            url=canonical,
            title=extracted.get("title") or "Untitled",
            author=extracted.get("author"),
            published_date=extracted.get("date"),
            domain=domain,
            content_hash=content_hash,
            raw_content=extracted["content"],
            fetch_timestamp=datetime.utcnow(),
        )

        logger.info(
            "scrape_success",
            url=url,
            source_id=source_id,
            content_length=len(source.raw_content),
        )

        return source

    except Exception as e:
        logger.error("scrape_error", url=url, error=str(e))
        return None


async def scrape_urls(urls: list[str], max_concurrent: int = 5) -> list[Source]:
    """
    Scrape multiple URLs concurrently.

    Args:
        urls: List of URLs to scrape
        max_concurrent: Maximum concurrent requests

    Returns:
        List of successfully scraped Source objects
    """
    logger.info("scrape_urls_started", count=len(urls))

    # Create semaphore for rate limiting
    semaphore = asyncio.Semaphore(max_concurrent)

    async def scrape_with_limit(url: str) -> Source | None:
        async with semaphore:
            return await scrape_url(url)

    # Scrape all URLs
    results = await asyncio.gather(*[scrape_with_limit(url) for url in urls])

    # Filter out None results
    sources = [s for s in results if s is not None]

    logger.info(
        "scrape_urls_complete",
        total=len(urls),
        successful=len(sources),
        failed=len(urls) - len(sources),
    )

    return sources


def deduplicate_sources(sources: list[Source]) -> list[Source]:
    """
    Deduplicate sources by content hash.

    Args:
        sources: List of sources

    Returns:
        Deduplicated list
    """
    seen_hashes: set[str] = set()
    seen_ids: set[str] = set()
    unique: list[Source] = []

    for source in sources:
        # Check both content hash and source ID
        if source.content_hash not in seen_hashes and source.source_id not in seen_ids:
            seen_hashes.add(source.content_hash)
            seen_ids.add(source.source_id)
            unique.append(source)

    logger.info(
        "deduplicate_sources",
        original=len(sources),
        unique=len(unique),
        duplicates=len(sources) - len(unique),
    )

    return unique

