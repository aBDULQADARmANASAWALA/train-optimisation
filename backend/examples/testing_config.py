"""
Examples and tests for configuration module.

Demonstrates how to:
- Load settings from environment
- Access configuration values
- Initialize logging
- Handle validation errors
"""

from app.config import settings, configure_logging, get_settings
import logging


def example_basic_settings_access():
    """Example: Access configuration values"""
    print("=== Basic Settings Access ===")
    print(f"Supabase URL: {settings.supabase_url}")
    print(f"Log Level: {settings.log_level}")
    print(f"Optimization Horizon: {settings.optimization_horizon_minutes} min")
    print(f"Rolling Step: {settings.rolling_step_minutes} min")
    print(f"Max Solver Time: {settings.max_solver_time_seconds} sec")
    print(f"Environment: {settings.environment}")


def example_logging_setup():
    """Example: Configure and use logging"""
    print("\n=== Logging Setup ===")

    # Configure logging based on settings
    configure_logging(settings)

    # Get logger
    logger = logging.getLogger(__name__)

    # Log at different levels
    logger.debug("This is a debug message (may not show if log level is INFO)")
    logger.info("Application initialized with settings")
    logger.warning("This is a warning")

    print("Logging configured. Check output above for log messages.")


def example_singleton_pattern():
    """Example: Verify singleton pattern works"""
    print("\n=== Singleton Pattern ===")

    settings1 = get_settings()
    settings2 = get_settings()

    print(f"settings1 is settings2: {settings1 is settings2}")
    print(f"Both point to same object (singleton): {id(settings1) == id(settings2)}")


def example_validation_demo():
    """
    Example: Show validation in action.

    NOTE: This requires proper environment variables to be set!
    If SUPABASE_URL or SUPABASE_KEY are missing, Settings initialization will fail.
    """
    print("\n=== Validation Examples ===")
    print("The following validations happen automatically:")
    print("1. Required fields: SUPABASE_URL, SUPABASE_KEY must not be empty")
    print("2. Numeric fields: optimization_horizon_minutes, etc. must be > 0")
    print("3. Log level: must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL")
    print("\nIf you try to create Settings with invalid values, pydantic will raise ValidationError")


def example_environment_override():
    """Example: Show how environment variables override defaults"""
    print("\n=== Environment Overrides ===")
    print(f"Default optimization_horizon_minutes: 60")
    print(f"From environment (if set): {settings.optimization_horizon_minutes}")
    print(f"Default log_level: INFO")
    print(f"From environment (if set): {settings.log_level}")
    print("\nSet environment variables to override defaults:")
    print("  export OPTIMIZATION_HORIZON_MINUTES=120")
    print("  export LOG_LEVEL=DEBUG")


if __name__ == "__main__":
    print("Configuration Examples and Tests\n")

    try:
        example_basic_settings_access()
        example_logging_setup()
        example_singleton_pattern()
        example_validation_demo()
        example_environment_override()

        print("\n✅ All examples completed successfully!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure you have set these environment variables:")
        print("  export SUPABASE_URL=https://your-project.supabase.co")
        print("  export SUPABASE_KEY=your-anon-key")
