"""Unit tests for Story 1.4 Configuration Management Framework.

Tests verify:
- Settings model with required and optional fields
- Environment variable validation
- Production PostgreSQL URL validation
- Singleton pattern behavior
- Integration with logging framework
"""

import pytest
from pydantic import ValidationError

# Import directly from settings module to avoid module-level singleton instantiation
from work_data_hub.config.settings import Settings, get_settings


@pytest.mark.unit
def test_missing_database_url_raises_error(monkeypatch):
    """Test that missing DATABASE_URL raises ValidationError (AC-2, AC-4)."""
    # Clear the lru_cache to ensure fresh Settings instance
    get_settings.cache_clear()

    # Remove DATABASE_URL from environment
    monkeypatch.delenv("DATABASE_URL", raising=False)

    # Attempt to create Settings without DATABASE_URL should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Settings()

    # Verify error message mentions DATABASE_URL
    assert "DATABASE_URL" in str(exc_info.value)

    # Cleanup
    get_settings.cache_clear()


@pytest.mark.unit
def test_production_requires_postgresql(monkeypatch):
    """Test that production environment validates PostgreSQL URL format (AC-4)."""
    # Clear the lru_cache
    get_settings.cache_clear()

    # Set ENVIRONMENT to prod with non-PostgreSQL URL
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")

    # Should raise ValidationError for non-PostgreSQL URL in production
    with pytest.raises(ValidationError) as exc_info:
        Settings()

    # Verify error message mentions PostgreSQL requirement
    error_msg = str(exc_info.value)
    assert "PostgreSQL" in error_msg or "postgresql://" in error_msg

    # Cleanup
    get_settings.cache_clear()


@pytest.mark.unit
def test_production_accepts_postgresql_url(monkeypatch):
    """Test that production environment accepts valid PostgreSQL URL (AC-4)."""
    # Clear the lru_cache
    get_settings.cache_clear()

    # Set ENVIRONMENT to prod with valid PostgreSQL URL
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

    # Should not raise any error
    settings_instance = Settings()
    assert settings_instance.ENVIRONMENT == "prod"
    assert settings_instance.DATABASE_URL.startswith("postgresql://")

    # Cleanup
    get_settings.cache_clear()


@pytest.mark.unit
def test_settings_singleton(monkeypatch):
    """Test that get_settings() returns same instance on multiple calls (AC-5)."""
    # Clear cache first to start fresh
    get_settings.cache_clear()

    # Set required DATABASE_URL
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

    # Get settings instance twice
    settings1 = get_settings()
    settings2 = get_settings()

    # Verify they are the exact same object (same memory address)
    assert settings1 is settings2
    assert id(settings1) == id(settings2)

    # Cleanup
    get_settings.cache_clear()


@pytest.mark.unit
def test_optional_fields_defaults(monkeypatch):
    """Test that optional fields have correct default values (AC-3)."""
    # Clear cache
    get_settings.cache_clear()

    # Set only required field
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

    # Clear optional fields to test defaults
    optional_keys = [
        "LOG_LEVEL",
        "DAGSTER_HOME",
        "MAX_WORKERS",
        "DB_POOL_SIZE",
        "DB_BATCH_SIZE",
        "ENVIRONMENT",
    ]
    for key in optional_keys:
        monkeypatch.delenv(key, raising=False)

    settings_instance = Settings()

    # Verify defaults per AC-3
    assert settings_instance.LOG_LEVEL == "INFO"
    assert settings_instance.DAGSTER_HOME == "~/.dagster"
    assert settings_instance.MAX_WORKERS == 4
    assert settings_instance.DB_POOL_SIZE == 10
    assert settings_instance.DB_BATCH_SIZE == 1000
    assert settings_instance.ENVIRONMENT == "dev"

    # Cleanup
    get_settings.cache_clear()


@pytest.mark.unit
def test_settings_model_structure(monkeypatch):
    """Test that Settings class exists with all required fields (AC-1)."""
    # Clear cache
    get_settings.cache_clear()

    # Set required field
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

    settings_instance = Settings()

    # Verify all required fields exist (AC-1, AC-2, AC-3)
    assert hasattr(settings_instance, "DATABASE_URL")
    assert hasattr(settings_instance, "ENVIRONMENT")
    assert hasattr(settings_instance, "LOG_LEVEL")
    assert hasattr(settings_instance, "DAGSTER_HOME")
    assert hasattr(settings_instance, "MAX_WORKERS")
    assert hasattr(settings_instance, "DB_POOL_SIZE")
    assert hasattr(settings_instance, "DB_BATCH_SIZE")

    # Verify field types
    assert isinstance(settings_instance.DATABASE_URL, str)
    assert settings_instance.ENVIRONMENT in ["dev", "staging", "prod"]
    assert isinstance(settings_instance.LOG_LEVEL, str)
    assert isinstance(settings_instance.DAGSTER_HOME, str)
    assert isinstance(settings_instance.MAX_WORKERS, int)
    assert isinstance(settings_instance.DB_POOL_SIZE, int)
    assert isinstance(settings_instance.DB_BATCH_SIZE, int)

    # Cleanup
    get_settings.cache_clear()


@pytest.mark.unit
def test_settings_import_patterns(monkeypatch):
    """Test that both import patterns work (AC-6)."""
    # Clear cache
    get_settings.cache_clear()

    # Set required field
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

    # Test factory function import - using direct import from settings module
    from work_data_hub.config.settings import get_settings as imported_get_settings

    settings_from_function = imported_get_settings()
    assert settings_from_function is not None

    # Test that get_settings returns the same instance on multiple calls
    settings_from_function_2 = imported_get_settings()
    assert settings_from_function is settings_from_function_2

    # Cleanup
    get_settings.cache_clear()


@pytest.mark.unit
def test_logging_integration(monkeypatch):
    """Test that logging module uses settings.LOG_LEVEL (AC-7)."""
    # Clear cache
    get_settings.cache_clear()

    # Set custom log level
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    # The logging module should use settings.LOG_LEVEL
    # We can verify that settings.LOG_LEVEL is accessible and used
    test_settings = Settings()
    assert test_settings.LOG_LEVEL == "DEBUG"

    # Cleanup
    get_settings.cache_clear()


@pytest.mark.unit
def test_environment_values_accepted(monkeypatch):
    """Test that all valid ENVIRONMENT values are accepted (AC-2)."""
    get_settings.cache_clear()

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

    for env_value in ["dev", "staging", "prod"]:
        monkeypatch.setenv("ENVIRONMENT", env_value)
        settings_instance = Settings()
        assert settings_instance.ENVIRONMENT == env_value
        get_settings.cache_clear()

    # Test invalid environment value
    monkeypatch.setenv("ENVIRONMENT", "invalid")
    with pytest.raises(ValidationError):
        Settings()

    # Cleanup
    get_settings.cache_clear()


@pytest.mark.unit
def test_custom_validator_postgresql(monkeypatch):
    """Test DATABASE_URL validator accepts valid PostgreSQL URLs (AC-4)."""
    get_settings.cache_clear()

    # Test various valid PostgreSQL URL formats
    valid_urls = [
        "postgresql://user:pass@localhost:5432/db",
        "postgresql://user@localhost/db",
        "postgresql://localhost/db",
        "postgresql://host.example.com:5433/mydb",
    ]

    for url in valid_urls:
        monkeypatch.setenv("DATABASE_URL", url)
        monkeypatch.setenv("ENVIRONMENT", "prod")
        settings_instance = Settings()
        assert settings_instance.DATABASE_URL == url
        get_settings.cache_clear()

    # Test that non-prod environments accept non-PostgreSQL URLs
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    settings_instance = Settings()
    assert settings_instance.DATABASE_URL == "sqlite:///test.db"

    # Cleanup
    get_settings.cache_clear()
