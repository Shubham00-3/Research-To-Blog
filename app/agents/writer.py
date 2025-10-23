"""Narrative Writer agent - composes coherent article with strict citation rules."""

import structlog

from app.data.models import Article, CitationMap, DraftSection, Outline, Source, Verdict
from app.llm.json_guard import ask_llm_text
from app.llm.prompts import WRITER_SYSTEM_PROMPT, format_sources_for_prompt
from app.tools.citation import create_citation_map, format_bibliography_markdown
from app.tools.quality import count_words, calculate_reading_level

logger = structlog.get_logger()


async def write_article(
    outline: Outline,
    drafts: list[DraftSection],
    sources: list[Source],
    verdicts: list[Verdict],
) -> Article:
    """
    Compose a complete article from verified claims and drafts.

    Args:
        outline: Article outline
        drafts: Draft sections
        sources: Source documents
        verdicts: Fact-check verdicts

    Returns:
        Article object with citations
    """
    logger.info("writer_started", num_sections=len(drafts))

    # Build context of verified claims
    verified_claims = [
        v for v in verdicts if v.verdict.value in ("supported", "common-knowledge")
    ]

    claims_context = "\n".join(
        f"- {v.claim_text} [Verdict: {v.verdict.value}, Confidence: {v.confidence:.2f}]"
        for v in verified_claims[:20]  # Limit to top 20 to avoid token overflow
    )

    # Build draft context
    draft_context = "\n\n".join(
        f"## {d.section_title}\n\n{d.content}" for d in drafts
    )

    # Format sources
    sources_formatted = format_sources_for_prompt(
        [
            {
                "title": s.title,
                "url": s.url,
                "author": s.author,
                "published_date": s.published_date,
            }
            for s in sources
        ]
    )

    # Build prompt
    user_prompt = f"""
Compose a complete, coherent article based on the following:

TITLE: {outline.title}

VERIFIED CLAIMS (use these as basis):
{claims_context}

DRAFT SECTIONS (improve and integrate):
{draft_context}

AVAILABLE SOURCES FOR CITATION:
{sources_formatted}

STRICT CITATION RULES:
1. EVERY sentence must either:
   a) Have inline citation(s): [1], [2][3], etc.
   b) Be tagged [COMMON] for common knowledge (use sparingly)
2. Use citations from the numbered source list (1-{len(sources)})
3. NEVER invent citation numbers
4. Stats, quotes, specific findings: MUST cite
5. Multiple sources strengthen credibility

WRITING GUIDELINES:
- Create smooth narrative flow between sections
- Use engaging, clear language
- Maintain consistent tone
- Break up long paragraphs
- Use subheadings where helpful
- Avoid redundancy from drafts

OUTPUT FORMAT:
# {outline.title}

[Article content with inline citations]

Do NOT include the bibliography (it will be added automatically).

Write the complete article now with proper citations.
""".strip()

    messages = [
        {"role": "system", "content": WRITER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Get article content
    content = await ask_llm_text(messages=messages, task="writer")

    # Create citation map
    citation_map = create_citation_map(content, sources)

    # Add bibliography to content
    bibliography = format_bibliography_markdown(citation_map.bibliography)
    full_content = f"{content}\n\n{bibliography}"

    # Calculate metrics
    word_count = count_words(content)
    reading_level = calculate_reading_level(content)

    article = Article(
        title=outline.title,
        content=full_content,
        citations=citation_map,
        word_count=word_count,
        reading_level=reading_level,
    )

    logger.info(
        "writer_complete",
        word_count=word_count,
        reading_level=f"{reading_level:.1f}",
        citation_coverage=f"{citation_map.coverage_rate:.2%}",
        num_citations=len(citation_map.bibliography),
    )

    return article

