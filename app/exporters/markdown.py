"""Markdown export with frontmatter and citations."""

import json
from pathlib import Path

import structlog

from app.data.models import ExportArtifact, SEOMetadata
from app.graph.state import PipelineState

logger = structlog.get_logger()


def generate_frontmatter(seo: SEOMetadata) -> str:
    """
    Generate YAML frontmatter for markdown.

    Args:
        seo: SEO metadata

    Returns:
        YAML frontmatter string
    """
    frontmatter = f"""---
title: "{seo.title}"
slug: {seo.slug}
description: "{seo.meta_description}"
keywords:
{chr(10).join(f"  - {kw}" for kw in seo.keywords)}
h1: "{seo.h1}"
---"""
    return frontmatter


def generate_json_ld_block(seo: SEOMetadata) -> str:
    """
    Generate JSON-LD script block.

    Args:
        seo: SEO metadata

    Returns:
        HTML script block with JSON-LD
    """
    json_str = json.dumps(seo.json_ld, indent=2)
    return f"""
<script type="application/ld+json">
{json_str}
</script>
"""


def export_markdown(
    state: PipelineState,
    include_frontmatter: bool = True,
    include_json_ld: bool = True,
) -> str:
    """
    Export article as markdown with metadata.

    Args:
        state: Final pipeline state
        include_frontmatter: Whether to include YAML frontmatter
        include_json_ld: Whether to include JSON-LD schema

    Returns:
        Complete markdown string
    """
    article = state.get("article")
    seo = state.get("seo_metadata")

    if not article:
        raise ValueError("No article in state")

    parts = []

    # Frontmatter
    if include_frontmatter and seo:
        parts.append(generate_frontmatter(seo))
        parts.append("")  # Blank line

    # JSON-LD
    if include_json_ld and seo:
        parts.append(generate_json_ld_block(seo))
        parts.append("")

    # Article content (already includes bibliography)
    parts.append(article.content)

    # Metadata footer
    parts.extend([
        "",
        "---",
        "",
        f"**Word Count:** {article.word_count}  ",
        f"**Reading Level:** {article.reading_level:.1f} (Flesch)  ",
        f"**Citation Coverage:** {article.citations.coverage_rate:.1%}  ",
        f"**Sources:** {len(article.citations.bibliography)}  ",
    ])

    return "\n".join(parts)


def export_json(state: PipelineState) -> dict:
    """
    Export complete state as JSON.

    Args:
        state: Final pipeline state

    Returns:
        JSON-serializable dict
    """
    return {
        "run_id": state.get("run_id"),
        "status": state.get("status"),
        "topic": state.get("topic_spec", {}).get("topic") if state.get("topic_spec") else None,
        "article": {
            "title": state.get("article").title if state.get("article") else None,
            "content": state.get("article").content if state.get("article") else None,
            "word_count": state.get("article").word_count if state.get("article") else 0,
            "reading_level": state.get("article").reading_level if state.get("article") else 0,
        } if state.get("article") else None,
        "seo": {
            "title": state.get("seo_metadata").title if state.get("seo_metadata") else None,
            "slug": state.get("seo_metadata").slug if state.get("seo_metadata") else None,
            "meta_description": state.get("seo_metadata").meta_description if state.get("seo_metadata") else None,
            "keywords": state.get("seo_metadata").keywords if state.get("seo_metadata") else [],
        } if state.get("seo_metadata") else None,
        "metrics": {
            "citation_coverage": state.get("quality_metrics").citation_coverage if state.get("quality_metrics") else 0,
            "unsupported_claim_rate": state.get("quality_metrics").unsupported_claim_rate if state.get("quality_metrics") else 0,
            "avg_fact_confidence": state.get("quality_metrics").avg_fact_confidence if state.get("quality_metrics") else 0,
            "total_claims": state.get("quality_metrics").total_claims if state.get("quality_metrics") else 0,
            "total_sources": state.get("quality_metrics").total_sources if state.get("quality_metrics") else 0,
        } if state.get("quality_metrics") else None,
        "run_metrics": {
            "time_elapsed_seconds": state.get("run_metrics").time_elapsed_seconds if state.get("run_metrics") else 0,
            "total_tokens": state.get("run_metrics").total_tokens if state.get("run_metrics") else 0,
            "groq_calls": state.get("run_metrics").groq_calls if state.get("run_metrics") else 0,
        } if state.get("run_metrics") else None,
        "logs": state.get("logs", []),
    }


def save_artifact(
    state: PipelineState,
    output_dir: Path,
    format: str = "md",
) -> ExportArtifact:
    """
    Save artifact to disk.

    Args:
        state: Final pipeline state
        output_dir: Output directory
        format: Export format ('md' or 'json')

    Returns:
        ExportArtifact with file path
    """
    run_id = state["run_id"]
    output_dir.mkdir(parents=True, exist_ok=True)

    if format == "md":
        content = export_markdown(state)
        file_path = output_dir / f"{run_id}.md"
        file_path.write_text(content, encoding="utf-8")

        artifact = ExportArtifact(
            run_id=run_id,
            format="md",
            content=content,
            file_path=str(file_path),
        )

    elif format == "json":
        content = export_json(state)
        file_path = output_dir / f"{run_id}.json"
        file_path.write_text(json.dumps(content, indent=2), encoding="utf-8")

        artifact = ExportArtifact(
            run_id=run_id,
            format="json",
            content=content,
            file_path=str(file_path),
        )

    else:
        raise ValueError(f"Unsupported format: {format}")

    logger.info("artifact_saved", run_id=run_id, format=format, path=str(file_path))

    return artifact

