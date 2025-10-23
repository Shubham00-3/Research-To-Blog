"""Style & QA Editor agent - refines article while preserving citations."""

import structlog

from app.data.models import Article
from app.llm.json_guard import ask_llm_text
from app.llm.prompts import EDITOR_SYSTEM_PROMPT
from app.tools.quality import calculate_reading_level, count_words

logger = structlog.get_logger()


async def edit_article(
    article: Article,
    target_reading_level: float = 60.0,
) -> Article:
    """
    Edit and refine an article for style and readability.

    Args:
        article: Article to edit
        target_reading_level: Target Flesch reading ease score

    Returns:
        Edited Article object
    """
    logger.info(
        "editor_started",
        current_reading_level=f"{article.reading_level:.1f}",
        target=f"{target_reading_level:.1f}",
    )

    # Build prompt
    user_prompt = f"""
Edit and refine this article for improved quality:

CURRENT ARTICLE:
{article.content}

CURRENT METRICS:
- Word count: {article.word_count}
- Reading level (Flesch): {article.reading_level:.1f}
- Citation coverage: {article.citations.coverage_rate:.2%}

TARGET READING LEVEL: {target_reading_level:.1f} (Flesch score)

EDITING TASKS:
1. Fix grammar, spelling, and punctuation
2. Improve sentence variety and flow
3. Remove redundancy and repetition
4. Ensure consistent tone and voice
5. Optimize for target reading level:
   - If too difficult (< 50): Simplify language, shorter sentences
   - If too simple (> 80): Add sophistication where appropriate
6. Enhance transitions between sections
7. Improve clarity and precision

CRITICAL RULES:
- PRESERVE ALL citation markers [1], [2], etc.
- DO NOT delete or renumber citations
- DO NOT remove the References section
- If a sentence lacks citation and needs one, flag it with [NEEDS_CITATION]

Return the edited article maintaining the same structure.
""".strip()

    messages = [
        {"role": "system", "content": EDITOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Get edited content
    edited_content = await ask_llm_text(messages=messages, task="writer")

    # Recalculate metrics
    new_word_count = count_words(edited_content)
    new_reading_level = calculate_reading_level(edited_content)

    # Update article
    article.content = edited_content
    article.word_count = new_word_count
    article.reading_level = new_reading_level

    logger.info(
        "editor_complete",
        word_count=new_word_count,
        reading_level=f"{new_reading_level:.1f}",
        improvement=f"{new_reading_level - article.reading_level:.1f}",
    )

    return article

