"""Command-line interface for the research-to-blog pipeline."""

import asyncio
import uuid
from pathlib import Path
from typing import Optional

import structlog
import typer
from rich.console import Console
from rich.progress import Progress, TextColumn
from rich.table import Table

from app.config import settings
from app.data.models import TopicSpec
from app.exporters.cms import publish_article
from app.graph.state import create_initial_state
from app.graph.workflow import run_pipeline

# Configure structlog for console output
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
)

logger = structlog.get_logger()

app = typer.Typer(help="Research-to-Blog Multi-Agent Pipeline")
console = Console()


@app.command()
def run(
    topic: str = typer.Argument(..., help="Research topic or question"),
    audience: str = typer.Option("general", help="Target audience"),
    goals: Optional[list[str]] = typer.Option(None, help="Specific goals (can specify multiple)"),
    keywords: Optional[list[str]] = typer.Option(None, help="Target keywords (can specify multiple)"),
    out: Path = typer.Option(settings.output_dir, help="Output directory"),
    publish: bool = typer.Option(False, help="Publish to configured CMS"),
):
    """
    Run the research-to-blog pipeline on a topic.

    Example:
        python -m app.cli.main run "How LLMs affect code review quality" --audience "engineering managers"
    """
    console.print(f"[bold cyan]Research-to-Blog Pipeline[/bold cyan]")
    console.print(f"Topic: [bold]{topic}[/bold]")
    console.print(f"Audience: {audience}\n")

    # Create topic spec
    topic_spec = TopicSpec(
        topic=topic,
        audience=audience,
        goals=goals or [],
        keywords=keywords or [],
    )

    # Generate run ID
    run_id = str(uuid.uuid4())[:8]

    # Create initial state
    initial_state = create_initial_state(run_id, topic_spec)

    # Run pipeline with progress indicator (no spinner for Windows compatibility)
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running pipeline...", total=None)

        # Run async pipeline
        final_state = asyncio.run(run_pipeline(initial_state))

        progress.update(task, completed=True)

    # Display results
    if final_state.get("status") == "completed":
        console.print("\n[bold green][OK] Pipeline completed successfully![/bold green]\n")

        # Display metrics
        metrics = final_state.get("quality_metrics")
        run_metrics = final_state.get("run_metrics")

        if metrics:
            table = Table(title="Quality Metrics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Citation Coverage", f"{metrics.citation_coverage:.1%}")
            table.add_row("Unsupported Claims", f"{metrics.unsupported_claim_rate:.1%}")
            table.add_row("Avg Confidence", f"{metrics.avg_fact_confidence:.2f}")
            table.add_row("Reading Level", f"{metrics.reading_level:.1f}")
            table.add_row("Total Claims", str(metrics.total_claims))
            table.add_row("Total Sources", str(metrics.total_sources))

            console.print(table)

        if run_metrics:
            console.print(f"\n[dim]Time: {run_metrics.time_elapsed_seconds:.1f}s | "
                         f"Tokens: {run_metrics.total_tokens} | "
                         f"API Calls: {run_metrics.groq_calls}[/dim]\n")

        # Publish or save
        if publish:
            console.print("[cyan]Publishing article...[/cyan]")
            result = asyncio.run(publish_article(final_state))
            console.print(f"[green]Published: {result}[/green]")
        else:
            console.print(f"[cyan]Saving to {out}...[/cyan]")
            from app.exporters.markdown import save_artifact

            md_artifact = save_artifact(final_state, out, format="md")
            json_artifact = save_artifact(final_state, out, format="json")

            console.print(f"[green][OK] Saved:[/green]")
            console.print(f"  • Markdown: {md_artifact.file_path}")
            console.print(f"  • JSON: {json_artifact.file_path}")

        # Display logs
        logs = final_state.get("logs", [])
        if logs:
            console.print("\n[bold]Pipeline Steps:[/bold]")
            for log in logs:
                console.print(f"  {log}")

    else:
        console.print(f"\n[bold red][FAIL] Pipeline failed: {final_state.get('error')}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def export(
    run_id: str = typer.Argument(..., help="Run ID to export"),
    format: str = typer.Option("md", help="Export format (md or json)"),
    out: Path = typer.Option(settings.output_dir, help="Output directory"),
):
    """
    Export a previous run's output.

    Note: This requires the run state to be cached (future feature).
    """
    console.print("[yellow]Export command not yet implemented - runs are auto-saved[/yellow]")
    console.print(f"Check {out} for saved outputs")


@app.command()
def config():
    """
    Display current configuration.
    """
    console.print("[bold cyan]Current Configuration:[/bold cyan]\n")

    table = Table()
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Orchestration Model", settings.groq_model_orch)
    table.add_row("Writer Model", settings.groq_model_writer)
    table.add_row("Embedding Backend", settings.embed_backend)
    table.add_row("Embedding Model", settings.embed_model_name)
    table.add_row("Tavily API", "[OK] Configured" if settings.tavily_api_key else "[X] Not configured")
    table.add_row("Publish Target", settings.publish_target)
    table.add_row("Output Directory", str(settings.output_dir))
    table.add_row("Min Citation Coverage", f"{settings.min_citation_coverage:.0%}")
    table.add_row("Target Reading Level", f"{settings.target_reading_level:.0f}")

    console.print(table)


@app.command()
def version():
    """Display version information."""
    from app import __version__

    console.print(f"[bold]Research-to-Blog Pipeline[/bold] v{__version__}")
    console.print("Zero-cost multi-agent pipeline with enforced citations")


if __name__ == "__main__":
    app()

