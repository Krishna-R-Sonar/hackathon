"""
Configuration management for Graph-Based AI Agent Memory.
Uses pydantic-settings to validate settings from environment variables and .env files.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # FalkorDB Database Configuration
    falkordb_host: str = "127.0.0.1"
    falkordb_port: int = 6379
    falkordb_graph_name: str = "agent_memory"
    falkordb_username: Optional[str] = None
    falkordb_password: Optional[str] = None

    # Memory Engine Configuration
    default_workspace_id: str = "default"
    log_level: str = "INFO"
    max_traversal_depth: int = 3
    max_retrieval_limit: int = 20
    context_token_budget: int = 4000

    # MCP Server Configuration
    mcp_server_name: str = "graph-agent-memory"
    mcp_server_version: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
