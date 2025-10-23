"""CMS publishing interfaces and implementations."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

import structlog

from app.config import settings
from app.exporters.markdown import save_artifact
from app.graph.state import PipelineState

logger = structlog.get_logger()


class Publisher(Protocol):
    """Protocol for CMS publishers."""

    async def publish(self, state: PipelineState) -> dict[str, str]:
        """
        Publish article to CMS.

        Args:
            state: Final pipeline state

        Returns:
            Dict with publish results (e.g., {"url": "...", "id": "..."})
        """
        ...


class DryRunPublisher:
    """Dry-run publisher that saves to local filesystem."""

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or settings.output_dir

    async def publish(self, state: PipelineState) -> dict[str, str]:
        """
        'Publish' by saving to local files.

        Args:
            state: Final pipeline state

        Returns:
            Dict with file paths
        """
        logger.info("dryrun_publish", run_id=state["run_id"])

        # Save both MD and JSON
        md_artifact = save_artifact(state, self.output_dir, format="md")
        json_artifact = save_artifact(state, self.output_dir, format="json")

        result = {
            "status": "dryrun",
            "markdown_path": md_artifact.file_path or "",
            "json_path": json_artifact.file_path or "",
        }

        logger.info("dryrun_publish_complete", **result)

        return result


class WordPressPublisher:
    """WordPress publisher (stub implementation)."""

    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        logger.warning("wordpress_publisher_stub_only")

    async def publish(self, state: PipelineState) -> dict[str, str]:
        """
        Publish to WordPress (stub).

        In production, would use WordPress REST API:
        - POST /wp-json/wp/v2/posts
        - Set title, content, excerpt, status=draft
        - Add meta fields and featured image

        Args:
            state: Final pipeline state

        Returns:
            Dict with post URL and ID
        """
        logger.warning("wordpress_publish_not_implemented")

        # Stub implementation
        article = state.get("article")
        seo = state.get("seo_metadata")

        # In production:
        # import httpx
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         f"{self.url}/wp-json/wp/v2/posts",
        #         headers={"Authorization": f"Bearer {self.token}"},
        #         json={
        #             "title": seo.title if seo else article.title,
        #             "content": article.content,
        #             "excerpt": seo.meta_description if seo else "",
        #             "status": "draft",
        #             "meta": {...},
        #         }
        #     )
        #     return {"url": response.json()["link"], "id": response.json()["id"]}

        return {
            "status": "stub",
            "message": "WordPress publishing not implemented",
            "title": seo.title if seo else (article.title if article else ""),
        }


class GhostPublisher:
    """Ghost CMS publisher (stub implementation)."""

    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        logger.warning("ghost_publisher_stub_only")

    async def publish(self, state: PipelineState) -> dict[str, str]:
        """
        Publish to Ghost (stub).

        In production, would use Ghost Admin API:
        - POST /ghost/api/v3/admin/posts/
        - Set title, html, custom_excerpt, status=draft
        - Add meta_title, meta_description, og_image

        Args:
            state: Final pipeline state

        Returns:
            Dict with post URL and ID
        """
        logger.warning("ghost_publish_not_implemented")

        article = state.get("article")
        seo = state.get("seo_metadata")

        # In production:
        # import httpx
        # import jwt  # for Ghost Admin API authentication
        # token = jwt.encode({...}, self.token, algorithm='HS256')
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         f"{self.url}/ghost/api/v3/admin/posts/",
        #         headers={"Authorization": f"Ghost {token}"},
        #         json={"posts": [{"title": ..., "html": ..., "status": "draft"}]}
        #     )
        #     return {"url": response.json()["posts"][0]["url"], ...}

        return {
            "status": "stub",
            "message": "Ghost publishing not implemented",
            "title": seo.title if seo else (article.title if article else ""),
        }


def get_publisher() -> Publisher:
    """
    Get the configured publisher.

    Returns:
        Publisher instance
    """
    target = settings.publish_target

    if target == "dryrun":
        return DryRunPublisher()

    elif target == "wordpress":
        if not settings.cms_url or not settings.cms_token:
            logger.warning("wordpress_credentials_missing_fallback_to_dryrun")
            return DryRunPublisher()
        return WordPressPublisher(settings.cms_url, settings.cms_token)

    elif target == "ghost":
        if not settings.cms_url or not settings.cms_token:
            logger.warning("ghost_credentials_missing_fallback_to_dryrun")
            return DryRunPublisher()
        return GhostPublisher(settings.cms_url, settings.cms_token)

    else:
        logger.warning("unknown_publisher_fallback_to_dryrun", target=target)
        return DryRunPublisher()


async def publish_article(state: PipelineState) -> dict[str, str]:
    """
    Publish article using configured publisher.

    Args:
        state: Final pipeline state

    Returns:
        Dict with publish results
    """
    publisher = get_publisher()
    return await publisher.publish(state)

