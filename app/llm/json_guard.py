"""JSON validation and retry logic for LLM outputs."""

import json
from typing import Any, Type, TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from app.llm.clients import GroqClient, get_groq_client
from app.llm.prompts import get_json_instruction

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)


async def ask_llm_json(
    messages: list[dict[str, str]],
    response_model: Type[T],
    client: GroqClient | None = None,
    task: str = "orch",
    max_retries: int = 3,
) -> T:
    """
    Ask LLM for a response and validate against a Pydantic model.

    This function:
    1. Appends JSON schema instruction to messages
    2. Requests JSON response format from Groq
    3. Validates response against Pydantic model
    4. Retries with error feedback on validation failure

    Args:
        messages: Chat messages
        response_model: Pydantic model class to validate against
        client: GroqClient instance (uses global if None)
        task: Task type for model routing
        max_retries: Maximum retry attempts

    Returns:
        Validated Pydantic model instance

    Raises:
        ValidationError: If validation fails after all retries
        ValueError: If response is not valid JSON
    """
    client = client or get_groq_client()

    # Add JSON instruction
    schema_name = response_model.__name__
    json_instruction = get_json_instruction(schema_name)

    # Append to system message or last user message
    enhanced_messages = messages.copy()
    if enhanced_messages and enhanced_messages[-1]["role"] == "user":
        enhanced_messages[-1]["content"] += f"\n\n{json_instruction}"
    else:
        enhanced_messages.append({"role": "user", "content": json_instruction})

    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            # Request with JSON response format
            response = await client.chat(
                messages=enhanced_messages,
                task=task,  # type: ignore
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from LLM")

            # Parse JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning("json_parse_error", error=str(e), content=content[:200])
                raise ValueError(f"Invalid JSON response: {e}")

            # Validate with Pydantic
            validated = response_model.model_validate(data)

            logger.info(
                "json_validation_success",
                model=schema_name,
                attempt=attempt + 1,
            )

            return validated

        except (ValidationError, ValueError) as e:
            last_error = e
            logger.warning(
                "json_validation_error",
                error=str(e),
                model=schema_name,
                attempt=attempt + 1,
                max_retries=max_retries,
            )

            if attempt < max_retries - 1:
                # Add error feedback for retry
                error_msg = f"""
The previous response had validation errors:
{str(e)}

Please provide a valid JSON response matching the {schema_name} schema exactly.
Ensure all required fields are present and have the correct types.
"""
                enhanced_messages.append({"role": "user", "content": error_msg})
            else:
                # Final attempt failed
                logger.error(
                    "json_validation_failed",
                    model=schema_name,
                    error=str(e),
                )
                raise

    # Should not reach here, but for type safety
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected error in ask_llm_json")


async def ask_llm_text(
    messages: list[dict[str, str]],
    client: GroqClient | None = None,
    task: str = "writer",
) -> str:
    """
    Ask LLM for a plain text response (e.g., for article writing).

    Args:
        messages: Chat messages
        client: GroqClient instance (uses global if None)
        task: Task type for model routing

    Returns:
        Text response from LLM
    """
    client = client or get_groq_client()

    response = await client.chat(messages=messages, task=task)  # type: ignore

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Empty response from LLM")

    return content

