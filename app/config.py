"""Configuration management using Pydantic Settings."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Required: Groq API
    groq_api_key: str = Field(..., description="Groq API key")

    # LLM Model Configuration
    groq_model_orch: str = Field(
        default="llama-3.1-8b-instant",
        description="Fast model for orchestration, planning, fact-checking",
    )
    groq_model_writer: str = Field(
        default="llama-3.1-70b-versatile",
        description="Stronger model for writing and editing",
    )
    groq_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    groq_max_tokens: int = Field(default=4096, ge=1)

    # Embedding Configuration
    embed_backend: Literal["fastembed", "sentence-transformers"] = Field(default="fastembed")
    embed_model_name: str = Field(default="BAAI/bge-small-en-v1.5")

    # Optional: Search API
    tavily_api_key: str | None = Field(default=None)

    # Optional: LangSmith tracing
    langchain_tracing_v2: bool = Field(default=False)
    langchain_api_key: str | None = Field(default=None)
    langchain_project: str = Field(default="research-to-blog")

    # Publishing Configuration
    publish_target: Literal["dryrun", "wordpress", "ghost"] = Field(default="dryrun")
    cms_url: str | None = Field(default=None)
    cms_token: str | None = Field(default=None)
    cms_username: str | None = Field(default=None)
    cms_password: str | None = Field(default=None)

    # Quality Gates
    min_citation_coverage: float = Field(default=0.95, ge=0.0, le=1.0)
    max_unsupported_claims: float = Field(default=0.05, ge=0.0, le=1.0)
    min_fact_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    target_reading_level: float = Field(default=60.0, description="Flesch reading ease score")

    # Rate Limiting and Budgets
    max_groq_rpm: int = Field(default=30)
    max_groq_tokens_per_min: int = Field(default=14000)
    max_pipeline_time_seconds: int = Field(default=600)
    max_pipeline_tokens: int = Field(default=100000)

    # Data Storage
    chroma_persist_dir: Path = Field(default=Path("./data/chroma"))
    cache_dir: Path = Field(default=Path("./data/cache"))
    output_dir: Path = Field(default=Path("./outputs"))

    # Logging
    log_level: str = Field(default="INFO")
    log_format: Literal["json", "console"] = Field(default="json")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()

