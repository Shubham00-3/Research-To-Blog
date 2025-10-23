"""Abstractive Summarizer agent - drafts content with citations."""

import structlog

from app.data.models import Claim, ClaimList, DraftSection, Outline, OutlineSection, Source
from app.llm.json_guard import ask_llm_json, ask_llm_text
from app.llm.prompts import SUMMARIZER_SYSTEM_PROMPT, format_sources_for_prompt
from app.tools.retrieval import index_sources, retrieve_for_query

logger = structlog.get_logger()


async def summarize_section(
    section: OutlineSection,
    sources: list[Source],
    section_index: int,
) -> DraftSection:
    """
    Draft content for a single section.

    Args:
        section: Outline section to draft
        sources: Available sources
        section_index: Section number (for logging)

    Returns:
        DraftSection with content and extracted claims
    """
    logger.info(
        "summarizer_section_started",
        section=section.title,
        index=section_index,
    )

    # Retrieve relevant content for this section
    query = f"{section.title}. {' '.join(section.key_questions)}"
    retrieved = await retrieve_for_query(query, n_results=10)

    # Build context from retrieved chunks
    context_chunks = []
    for i, result in enumerate(retrieved[:5], 1):
        context_chunks.append(
            f"[Source {i}] {result.metadata.get('title', 'Unknown')}\n{result.text}\n"
        )

    context = "\n---\n".join(context_chunks)

    # Format sources for citation
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
Draft content for this section:

Section: {section.title}

Key questions to address:
{chr(10).join(f"- {q}" for q in section.key_questions)}

Target word count: ~{section.estimated_words} words

Available sources:
{sources_formatted}

Relevant context from sources:
{context}

IMPORTANT RULES:
1. Use inline bracket citations [1], [2] for all non-obvious claims
2. ONLY cite sources from the provided list (1-{len(sources)})
3. NEVER invent citation numbers
4. Use multiple citations [1][2] when appropriate
5. Write engaging, clear prose appropriate for the audience

Draft the section content now, including inline citations.
""".strip()

    messages = [
        {"role": "system", "content": SUMMARIZER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Get draft content
    content = await ask_llm_text(messages=messages, task="writer")

    # Now extract claims from the draft
    claims_prompt = f"""
Extract atomic, verifiable claims from this draft:

{content}

For each claim:
- Make it specific and testable
- Identify which sources support it
- Mark if it needs citation

Return JSON matching the ClaimList schema with extracted claims.
""".strip()

    claims_messages = [
        {"role": "system", "content": "You are a fact-checking assistant."},
        {"role": "user", "content": claims_prompt},
    ]

    claim_list = await ask_llm_json(
        messages=claims_messages,
        response_model=ClaimList,
        task="orch",
    )

    # Count words
    word_count = len(content.split())

    draft = DraftSection(
        section_title=section.title,
        content=content,
        claims=claim_list.claims,
        word_count=word_count,
    )

    logger.info(
        "summarizer_section_complete",
        section=section.title,
        word_count=word_count,
        num_claims=len(claim_list.claims),
    )

    return draft


async def summarize_article(
    outline: Outline,
    sources: list[Source],
) -> list[DraftSection]:
    """
    Draft all sections of an article.

    Args:
        outline: Article outline
        sources: Available sources

    Returns:
        List of DraftSection objects
    """
    logger.info("summarizer_started", num_sections=len(outline.sections))

    # Index sources for retrieval
    await index_sources(sources)

    # Draft each section
    drafts = []
    for i, section in enumerate(outline.sections):
        draft = await summarize_section(section, sources, i)
        drafts.append(draft)

    total_words = sum(d.word_count for d in drafts)
    total_claims = sum(len(d.claims) for d in drafts)

    logger.info(
        "summarizer_complete",
        num_sections=len(drafts),
        total_words=total_words,
        total_claims=total_claims,
    )

    return drafts

