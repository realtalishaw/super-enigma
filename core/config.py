"""
Configuration settings for the workflow automation engine.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Database settings
    database_url: str = Field(
        default="postgresql://user:password@localhost/workflow_automation",
        description="PostgreSQL database connection URL"
    )
    
    # Redis settings
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL"
    )
    
    # Composio API settings
    composio_api_key: Optional[str] = Field(
        default=None,
        description="Composio API key for fetching catalog data"
    )
    composio_base_url: str = Field(
        default="https://api.composio.dev",
        description="Composio API base URL"
    )
    
    # Anthropic API settings
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude LLM access"
    )
    
    # Groq API settings
    groq_api_key: Optional[str] = Field(
        default=None,
        description="Groq API key for fast LLM tool retrieval"
    )
    
    # Tool selection limits for RAG workflow
    max_triggers: int = Field(
        default=10,
        description="Maximum number of triggers to include in Claude context"
    )
    max_actions: int = Field(
        default=20,
        description="Maximum number of actions to include in Claude context"
    )
    max_providers: int = Field(
        default=8,
        description="Maximum number of providers to include in Claude context"
    )
    
    # Claude API rate limiting
    claude_rate_limit_delay: float = Field(
        default=2.0,
        description="Base delay in seconds between Claude API retries"
    )
    max_rate_limit_delay: float = Field(
        default=30.0,
        description="Maximum delay in seconds between Claude API retries"
    )
    
    # Application settings
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # Scheduler settings
    scheduler_url: str = Field(
        default="http://localhost:8003",
        description="Scheduler service URL"
    )
    
    # API settings
    api_host: str = Field(
        default="0.0.0.0",
        description="API server host"
    )
    api_port: int = Field(
        default=8000,
        description="API server port"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Create global settings instance
settings = Settings()
