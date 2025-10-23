"""SEO Agent - optimizes article for search engines."""

import re
from datetime import datetime

import structlog
from slugify import slugify

from app.data.models import Article, SEOMetadata
from app.llm.json_guard import ask_llm_json
from app.llm.prompts import SEO_SYSTEM_PROMPT

logger = structlog.get_logger()


async def optimize_seo(article: Article, author: str = "Research Bot") -> SEOMetadata:
    """
    Generate SEO metadata for an article.

    Args:
        article: Article to optimize
        author: Article author name

    Returns:
        SEOMetadata object
    """
    logger.info("seo_started", title=article.title)

    # Extract H2 headings from content
    h2_pattern = r'^##\s+(.+)$'
    h2_tags = re.findall(h2_pattern, article.content, re.MULTILINE)

    # Build prompt
    user_prompt = f"""
Create SEO optimization metadata for this article:

TITLE: {article.title}

CONTENT PREVIEW:
{article.content[:1000]}...

CURRENT H2 HEADINGS:
{chr(10).join(f"- {h2}" for h2 in h2_tags)}

WORD COUNT: {article.word_count}

Generate SEO metadata including:

1. SEO Title (max 60 characters, includes primary keyword)
2. URL Slug (URL-friendly, lowercase with hyphens)
3. Meta Description (150-160 characters, compelling, includes keyword)
4. Target Keywords (5-10 relevant keywords/phrases)
5. H1 tag (main heading, may differ slightly from title)
6. Internal link suggestions (3-5 related topics for internal linking)

Best practices:
- Natural keyword integration
- Clear value proposition
- Compelling call-to-action in meta description
- Mobile-friendly structure

Return JSON with these fields:
- title (string, max 60 chars)
- slug (string)
- meta_description (string, 150-160 chars)
- keywords (list of strings)
- h1 (string)
- internal_links (list of dicts with 'anchor' and 'topic' keys)
""".strip()

    messages = [
        {"role": "system", "content": SEO_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Define response model
    from pydantic import BaseModel, Field

    class SEOResponse(BaseModel):
        title: str = Field(..., max_length=60)
        slug: str
        meta_description: str = Field(..., min_length=150, max_length=160)
        keywords: list[str]
        h1: str
        internal_links: list[dict[str, str]] = Field(default_factory=list)

    # Get SEO data
    response = await ask_llm_json(
        messages=messages,
        response_model=SEOResponse,
        task="orch",
    )

    # Generate slug from title if LLM didn't provide one
    if not response.slug:
        response.slug = slugify(article.title)

    # Generate JSON-LD schema
    json_ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": response.title,
        "description": response.meta_description,
        "author": {
            "@type": "Person",
            "name": author,
        },
        "datePublished": datetime.utcnow().isoformat(),
        "dateModified": datetime.utcnow().isoformat(),
        "wordCount": article.word_count,
        "keywords": ", ".join(response.keywords),
    }

    seo_metadata = SEOMetadata(
        title=response.title,
        slug=response.slug,
        meta_description=response.meta_description,
        keywords=response.keywords,
        h1=response.h1,
        h2_tags=h2_tags,
        internal_links=response.internal_links,
        json_ld=json_ld,
    )

    logger.info(
        "seo_complete",
        title=seo_metadata.title,
        slug=seo_metadata.slug,
        num_keywords=len(seo_metadata.keywords),
    )

    return seo_metadata

