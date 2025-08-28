"""
Tests for the core configuration module.
"""
import pytest
import os
from unittest.mock import patch
from core.config import Settings, settings


class TestSettings:
    """Test the Settings class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        with patch.dict(os.environ, {}, clear=True):
            test_settings = Settings()
            
            assert test_settings.database_url == "postgresql://user:password@localhost/workflow_automation"
            assert test_settings.redis_url == "redis://localhost:6379"
            assert test_settings.composio_base_url == "https://api.composio.dev"
            assert test_settings.debug is False
            assert test_settings.log_level == "INFO"
            assert test_settings.api_host == "0.0.0.0"
            assert test_settings.api_port == 8000

    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        test_env = {
            "DATABASE_URL": "postgresql://test:test@localhost/test_db",
            "REDIS_URL": "redis://test:6379",
            "COMPOSIO_API_KEY": "test_key_123",
            "DEBUG": "true",
            "LOG_LEVEL": "DEBUG"
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            test_settings = Settings()
            
            assert test_settings.database_url == "postgresql://test:test@localhost/test_db"
            assert test_settings.redis_url == "redis://test:6379"
            assert test_settings.composio_api_key == "test_key_123"
            assert test_settings.debug is True
            assert test_settings.log_level == "DEBUG"

    def test_optional_composio_api_key(self):
        """Test that composio_api_key is optional."""
        with patch.dict(os.environ, {}, clear=True):
            test_settings = Settings()
            assert test_settings.composio_api_key is None

    def test_settings_instance(self):
        """Test that the global settings instance exists."""
        assert isinstance(settings, Settings)
        assert hasattr(settings, 'database_url')
        assert hasattr(settings, 'redis_url')
        assert hasattr(settings, 'composio_base_url')

    def test_field_descriptions(self):
        """Test that field descriptions are set."""
        # Check that fields have descriptions using the class, not instance
        assert Settings.model_fields['database_url'].description == "PostgreSQL database connection URL"
        assert Settings.model_fields['redis_url'].description == "Redis connection URL"
        assert Settings.model_fields['composio_api_key'].description == "Composio API key for fetching catalog data"

    def test_case_insensitive_config(self):
        """Test that the config is case insensitive."""
        test_env = {
            "database_url": "postgresql://test:test@localhost/test_db",
            "DATABASE_URL": "postgresql://override:override@localhost/override_db"
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            test_settings = Settings()
            # Should use the last value set
            assert test_settings.database_url == "postgresql://override:override@localhost/override_db"

    def test_invalid_boolean_environment_variable(self):
        """Test handling of invalid boolean environment variables."""
        test_env = {
            "DEBUG": "invalid_boolean"
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            # Pydantic v2 is strict about validation, so this should raise an error
            with pytest.raises(Exception):
                test_settings = Settings()

    def test_invalid_integer_environment_variable(self):
        """Test handling of invalid integer environment variables."""
        test_env = {
            "API_PORT": "invalid_port"
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            # Pydantic v2 is strict about validation, so this should raise an error
            with pytest.raises(Exception):
                test_settings = Settings()
