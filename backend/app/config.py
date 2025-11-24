"""
Configuration management for Agent Profiler
Loads settings from environment variables
"""

from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Google Cloud
    google_cloud_project: str = "client-profiler-473903"
    vertex_ai_location: str = "us-central1"
    gcs_bucket_name: str = "client-profiler-473903-agent-profiler-data"

    # Database
    database_url: str

    # Redis
    redis_host: str
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # Gemini Models
    gemini_flash_model: str = "gemini-2.0-flash-exp"
    gemini_pro_model: str = "gemini-1.5-pro"

    # Authentication
    google_oauth_client_id: str
    google_oauth_client_secret: str
    allowed_domain: str = "enterprisesight.com"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    enable_cors: bool = True
    cors_origins: str = "http://localhost:3000"

    # Agent Configuration
    agent_timeout_seconds: int = 300
    max_agent_retries: int = 3
    enable_agent_logging: bool = True
    enable_sql_query_logging: bool = True
    enable_llm_conversation_logging: bool = True

    # CRM Configuration
    salesforce_api_version: str = "v60.0"
    crm_sync_batch_size: int = 100
    crm_rate_limit_buffer: float = 0.1

    # Feature Flags
    enable_csv_upload: bool = True
    enable_salesforce_connector: bool = True
    enable_wealthbox_connector: bool = False
    enable_redtail_connector: bool = False
    enable_junxure_connector: bool = False

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into list"""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.app_env == "development"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
