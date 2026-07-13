"""
Configuration management for the application.

This module provides a centralized, type-safe configuration system using Pydantic Settings.
All configuration values are loaded from environment variables (via .env file) and validated
on application startup. The configuration includes connection settings for external services
(Qdrant, OpenAI, Anthropic), application settings, and Qdrant 1.16 ACORN feature settings.

The Settings class automatically:
- Loads values from a .env file in the project root
- Validates all settings on startup
- Provides type-safe access to configuration values
- Supports case-insensitive environment variable names
"""

from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration settings.
    
    This class manages all configuration for the automotive part matcher application.
    Settings are loaded from environment variables and validated on instantiation.
    All connection settings are required, while application and feature settings
    have sensible defaults.
    
    Qdrant 1.16 ACORN Feature:
    ACORN (Approximate Clustering for Retrieval Networks) is a Qdrant 1.16 feature
    that improves search performance by using approximate clustering. The max_selectivity
    threshold controls the maximum selectivity allowed before falling back to exact search.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    
    # Connection settings (required, no defaults)
    qdrant_url: str = Field(
        ...,
        description="Qdrant Cloud connection URL for the vector database instance"
    )
    
    qdrant_api_key: Optional[str] = Field(
        default=None,
        description="API key for authenticating with Qdrant Cloud (optional for local instances)"
    )
    
    openai_api_key: str = Field(
        ...,
        description="API key for authenticating with OpenAI services"
    )
    
    anthropic_api_key: str = Field(
        ...,
        description="API key for authenticating with Anthropic Claude services"
    )
    
    # Application settings (with defaults)
    llm_provider: str = Field(
        default="claude",
        description="LLM provider selection. Must be either 'claude' or 'openai'"
    )
    
    collection_name: str = Field(
        default="automotive_connectors",
        description="Name of the Qdrant collection storing automotive connector embeddings"
    )
    
    embedding_model: str = Field(
        default="text-embedding-3-large",
        description="Name of the embedding model to use for vector generation"
    )
    
    embedding_dimensions: int = Field(
        default=3072,
        description="Number of dimensions in the embedding vectors. Must match the model output (3072 for text-embedding-3-large)"
    )
    
    # LLM extraction: use 0.0 for consistent results (same input → same extracted specs)
    extraction_temperature: float = Field(
        default=0.0,
        description="Temperature for requirement extraction (0.0 = deterministic, same doc → same results)",
        ge=0.0,
        le=2.0,
    )

    # Qdrant 1.16 ACORN settings (with defaults)
    acorn_enabled: bool = Field(
        default=True,
        description="Enable Qdrant 1.16 ACORN (Approximate Clustering for Retrieval Networks) feature for improved search performance"
    )
    
    acorn_max_selectivity: float = Field(
        default=0.4,
        description="ACORN maximum selectivity threshold (0.0-1.0). Controls when to fall back to exact search"
    )

    # Neo4j graph database (required for graph / disruption features)
    neo4j_uri: Optional[str] = Field(
        default=None,
        description="Neo4j connection URI (neo4j+s://... or bolt://...). Required for graph features.",
    )

    neo4j_username: str = Field(
        default="neo4j",
        description="Neo4j database username",
    )

    neo4j_password: Optional[str] = Field(
        default=None,
        description="Neo4j database password",
    )

    @property
    def neo4j_enabled(self) -> bool:
        """True when Neo4j URI and password are configured."""
        return bool(self.neo4j_uri and self.neo4j_password)
    
    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """Validate that LLM provider is either 'claude' or 'openai'."""
        if v.lower() not in ("claude", "openai"):
            raise ValueError("LLM provider must be either 'claude' or 'openai'")
        return v.lower()
    
    @field_validator("embedding_dimensions")
    @classmethod
    def validate_embedding_dimensions(cls, v: int) -> int:
        """Validate that embedding dimensions match the model output (3072 for text-embedding-3-large)."""
        if v != 3072:
            raise ValueError(
                f"Embedding dimensions must be 3072 for text-embedding-3-large model, got {v}"
            )
        return v
    
    @field_validator("acorn_max_selectivity")
    @classmethod
    def validate_acorn_selectivity(cls, v: float) -> float:
        """Validate that ACORN selectivity is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(
                f"ACORN max selectivity must be between 0.0 and 1.0, got {v}"
            )
        return v


# Module-level singleton instance
settings = Settings()
