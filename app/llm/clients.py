"""LLM client implementations with Groq."""

import asyncio
import time
from typing import Any, Literal

import structlog
from groq import Groq, AsyncGroq
from groq.types.chat import ChatCompletion

from app.config import settings

logger = structlog.get_logger()


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, max_calls_per_minute: int, max_tokens_per_minute: int):
        self.max_calls = max_calls_per_minute
        self.max_tokens = max_tokens_per_minute
        self.call_times: list[float] = []
        self.token_usage: list[tuple[float, int]] = []
        self._lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 1000) -> None:
        """Wait until rate limit allows the call."""
        async with self._lock:
            now = time.time()

            # Remove old entries (> 60 seconds ago)
            self.call_times = [t for t in self.call_times if now - t < 60]
            self.token_usage = [(t, tokens) for t, tokens in self.token_usage if now - t < 60]

            # Check call limit
            while len(self.call_times) >= self.max_calls:
                await asyncio.sleep(1)
                now = time.time()
                self.call_times = [t for t in self.call_times if now - t < 60]

            # Check token limit
            current_tokens = sum(tokens for _, tokens in self.token_usage)
            while current_tokens + estimated_tokens > self.max_tokens:
                await asyncio.sleep(1)
                now = time.time()
                self.token_usage = [
                    (t, tokens) for t, tokens in self.token_usage if now - t < 60
                ]
                current_tokens = sum(tokens for _, tokens in self.token_usage)

            # Record this call
            self.call_times.append(now)
            self.token_usage.append((now, estimated_tokens))


class GroqClient:
    """Groq API client with model routing and rate limiting."""

    def __init__(
        self,
        api_key: str | None = None,
        model_orch: str | None = None,
        model_writer: str | None = None,
    ):
        self.api_key = api_key or settings.groq_api_key
        self.model_orch = model_orch or settings.groq_model_orch
        self.model_writer = model_writer or settings.groq_model_writer

        self.client = Groq(api_key=self.api_key)
        self.async_client = AsyncGroq(api_key=self.api_key)

        # Rate limiter
        self.rate_limiter = RateLimiter(
            max_calls_per_minute=settings.max_groq_rpm,
            max_tokens_per_minute=settings.max_groq_tokens_per_min,
        )

        self.total_calls = 0
        self.total_tokens = 0

    def get_model_for_task(
        self, task: Literal["orch", "writer"]
    ) -> str:
        """Get the appropriate model for a task type."""
        return self.model_writer if task == "writer" else self.model_orch

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        task: Literal["orch", "writer"] = "orch",
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
        retry_count: int = 3,
        retry_delay: float = 1.0,
    ) -> ChatCompletion:
        """
        Send a chat completion request to Groq.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Explicit model name (overrides task-based routing)
            task: Task type for model routing ('orch' or 'writer')
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Optional response format (e.g., {"type": "json_object"})
            retry_count: Number of retries on failure
            retry_delay: Base delay between retries (exponential backoff)

        Returns:
            ChatCompletion response
        """
        model = model or self.get_model_for_task(task)
        temperature = temperature if temperature is not None else settings.groq_temperature
        max_tokens = max_tokens or settings.groq_max_tokens

        # Estimate tokens for rate limiting (rough heuristic)
        estimated_tokens = sum(len(m.get("content", "")) for m in messages) // 4 + max_tokens

        for attempt in range(retry_count):
            try:
                # Rate limiting
                await self.rate_limiter.acquire(estimated_tokens)

                # Make the API call
                logger.info(
                    "groq_chat_request",
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    attempt=attempt + 1,
                )

                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }

                if response_format:
                    kwargs["response_format"] = response_format

                response = await asyncio.to_thread(
                    self.client.chat.completions.create, **kwargs
                )

                # Track usage
                self.total_calls += 1
                if response.usage:
                    self.total_tokens += response.usage.total_tokens

                logger.info(
                    "groq_chat_success",
                    model=model,
                    tokens=response.usage.total_tokens if response.usage else 0,
                )

                return response

            except Exception as e:
                logger.warning(
                    "groq_chat_error",
                    error=str(e),
                    attempt=attempt + 1,
                    retry_count=retry_count,
                )

                if attempt < retry_count - 1:
                    delay = retry_delay * (2**attempt)  # Exponential backoff
                    await asyncio.sleep(delay)
                else:
                    raise

        raise RuntimeError(f"Failed to complete Groq request after {retry_count} attempts")

    def get_usage_stats(self) -> dict[str, int]:
        """Get usage statistics."""
        return {
            "total_calls": self.total_calls,
            "total_tokens": self.total_tokens,
        }


# Global client instance
_groq_client: GroqClient | None = None


def get_groq_client() -> GroqClient:
    """Get or create the global Groq client."""
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient()
    return _groq_client

