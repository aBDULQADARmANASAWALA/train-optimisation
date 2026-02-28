import logging
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.
    Uses Pydantic BaseSettings for validation and type safety.
    """

    # Supabase Configuration
    supabase_url: str = Field(
        ..., description="Supabase project URL"
    )
    supabase_key: str = Field(
        ..., description="Supabase API key"
    )

    # Direct PostgreSQL connection string (get from Supabase dashboard > Settings > Database)
    # Overrides the URL constructed from supabase_url when set
    database_url: Optional[str] = Field(
        default=None, description="Direct PostgreSQL connection string"
    )

    # Optimization Configuration
    optimization_horizon_minutes: int = Field(
        default=60, description="Optimization planning horizon in minutes"
    )
    rolling_step_minutes: int = Field(
        default=5, description="Rolling window step size in minutes"
    )
    max_solver_time_seconds: float = Field(
        default=30.0, description="Maximum solver execution time in seconds"
    )

    # Environment
    environment: str = Field(
        default="development", description="Application environment (development/staging/production)"
    )

    # Logging
    log_level: str = Field(
        default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @field_validator("supabase_url", "supabase_key")
    @classmethod
    def validate_required_fields(cls, v):
        """Ensure required Supabase fields are provided"""
        if not v or not v.strip():
            raise ValueError("Supabase credentials are required")
        return v

    @field_validator("optimization_horizon_minutes", "rolling_step_minutes", "max_solver_time_seconds")
    @classmethod
    def validate_positive_numbers(cls, v):
        """Ensure numeric settings are positive"""
        if v <= 0:
            raise ValueError("Must be a positive number")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Ensure log level is valid"""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get singleton settings instance.
    Uses lru_cache to ensure only one Settings object is created.

    Returns:
        Settings: Singleton configuration object
    """
    return Settings()


def configure_logging(settings: Settings) -> None:
    """
    Configure application logging based on settings.

    Args:
        settings: Settings object containing log_level configuration
    """
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("supabase").setLevel(logging.INFO)


# Export singleton instance for use throughout the application
settings = get_settings()
