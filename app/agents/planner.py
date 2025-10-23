"""Topic Planner agent - creates article outline."""

import structlog

from app.data.models import Outline, OutlineSection, TopicSpec
from app.llm.json_guard import ask_llm_json
from app.llm.prompts import PLANNER_SYSTEM_PROMPT

logger = structlog.get_logger()


async def plan_article(topic_spec: TopicSpec) -> Outline:
    """
    Create an article outline from a topic specification.

    Args:
        topic_spec: Topic specification with topic, audience, goals

    Returns:
        Outline object with sections and structure
    """
    logger.info("planner_started", topic=topic_spec.topic, audience=topic_spec.audience)

    # Build prompt
    user_prompt = f"""
Create a comprehensive article outline for the following topic:

Topic: {topic_spec.topic}
Audience: {topic_spec.audience}

Goals:
{chr(10).join(f"- {goal}" for goal in topic_spec.goals) if topic_spec.goals else "- Provide comprehensive coverage"}

Constraints:
{chr(10).join(f"- {k}: {v}" for k, v in topic_spec.constraints.items()) if topic_spec.constraints else "- None specified"}

Target keywords: {', '.join(topic_spec.keywords) if topic_spec.keywords else "N/A"}

Create an outline with:
- An engaging article title
- 4-6 main sections with clear titles
- Key questions to answer in each section
- Expected claims that will need verification
- Estimated word count per section (total ~2000-3000 words)
- Rationale for this structure

Return JSON matching the Outline schema.
""".strip()

    messages = [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Get outline from LLM
    outline = await ask_llm_json(
        messages=messages,
        response_model=Outline,
        task="orch",
    )

    logger.info(
        "planner_complete",
        title=outline.title,
        num_sections=len(outline.sections),
        total_words=outline.estimated_total_words,
    )

    return outline

