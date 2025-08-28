"""
Tests for the core catalog service.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import json
from core.catalog.cache import RedisCacheStore
from core.catalog.database_service import CatalogDatabaseService
from core.catalog.composio_client import ComposioCatalogClient
import asyncio


class TestRedisCacheStore:
    """Test the RedisCacheStore class."""
    
    def test_redis_cache_store_initialization(self):
        """Test RedisCacheStore initialization."""
        with patch('core.catalog.cache.redis.asyncio.Redis') as mock_redis:
            mock_redis_instance = Mock()
            mock_redis.return_value = mock_redis_instance
            
            cache = RedisCacheStore(mock_redis_instance, key_prefix="test_cache")
            
            assert cache.redis == mock_redis_instance
            assert cache.key_prefix == "test_cache"
            assert cache.default_ttl == 3600

    @patch('core.catalog.cache.redis.asyncio.Redis')
    async def test_cache_set_get(self, mock_redis):
        """Test cache set and get operations."""
        mock_redis_instance = AsyncMock()
        mock_redis.return_value = mock_redis_instance
        
        cache = RedisCacheStore(mock_redis_instance, key_prefix="test_cache")
        
        # Test set
        result = await cache.set("test_key", {"data": "value"}, ttl=300)
        assert result is True
        mock_redis_instance.setex.assert_called_once_with("test_cache:test_key", 300, '{"data": "value"}')
        
        # Test get
        mock_redis_instance.get.return_value = '{"data": "value"}'
        result = await cache.get("test_key")
        assert result == {"data": "value"}
        mock_redis_instance.get.assert_called_once_with("test_cache:test_key")

    @patch('core.catalog.cache.redis.Redis')
    def test_cache_get_missing(self, mock_redis):
        """Test cache get with missing key."""
        mock_redis_instance = Mock()
        mock_redis_instance.get.return_value = None
        mock_redis.return_value = mock_redis_instance
        
        cache = CatalogCache(redis_url="redis://localhost:6379")
        
        result = cache.get("missing_key")
        assert result is None

    @patch('core.catalog.cache.redis.Redis')
    def test_cache_delete(self, mock_redis):
        """Test cache delete operation."""
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        
        cache = CatalogCache(redis_url="redis://localhost:6379")
        
        cache.delete("test_key")
        mock_redis_instance.delete.assert_called_once_with("test_key")

    @patch('core.catalog.cache.redis.Redis')
    def test_cache_exists(self, mock_redis):
        """Test cache exists operation."""
        mock_redis_instance = Mock()
        mock_redis_instance.exists.return_value = True
        mock_redis.return_value = mock_redis_instance
        
        cache = CatalogCache(redis_url="redis://localhost:6379")
        
        result = cache.exists("test_key")
        assert result is True
        mock_redis_instance.exists.assert_called_once_with("test_key")

    @patch('core.catalog.cache.redis.Redis')
    def test_cache_clear(self, mock_redis):
        """Test cache clear operation."""
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        
        cache = CatalogCache(redis_url="redis://localhost:6379")
        
        cache.clear()
        mock_redis_instance.flushdb.assert_called_once()

    @patch('core.catalog.cache.redis.Redis')
    def test_cache_ttl(self, mock_redis):
        """Test cache TTL operations."""
        mock_redis_instance = Mock()
        mock_redis_instance.ttl.return_value = 150
        mock_redis.return_value = mock_redis_instance
        
        cache = CatalogCache(redis_url="redis://localhost:6379")
        
        result = cache.ttl("test_key")
        assert result == 150
        mock_redis_instance.ttl.assert_called_once_with("test_key")


class TestCatalogDatabaseService:
    """Test the CatalogDatabaseService class."""
    
    def test_database_service_initialization(self):
        """Test CatalogDatabaseService initialization."""
        with patch('core.catalog.database_service.create_engine') as mock_engine, \
             patch('core.catalog.database_service.sessionmaker') as mock_sessionmaker:
            
            service = CatalogDatabaseService(database_url="sqlite:///:memory:")
            
            assert service.database_url == "sqlite:///:memory:"
            mock_engine.assert_called_once()

    @patch('core.catalog.database_service.create_engine')
    @patch('core.catalog.database_service.sessionmaker')
    def test_get_session(self, mock_sessionmaker, mock_engine):
        """Test getting database session."""
        mock_session = Mock()
        mock_sessionmaker.return_value = mock_session
        
        service = CatalogDatabaseService(database_url="sqlite:///:memory:")
        
        with service.get_session() as session:
            assert session == mock_session

    @patch('core.catalog.database_service.create_engine')
    @patch('core.catalog.database_service.sessionmaker')
    def test_save_tool(self, mock_sessionmaker, mock_engine):
        """Test saving a tool to database."""
        mock_session = Mock()
        mock_sessionmaker.return_value = mock_session
        
        service = CatalogDatabaseService(database_url="sqlite:///:memory:")
        
        tool_data = {
            "id": "tool_123",
            "name": "Test Tool",
            "description": "A test tool",
            "category": "test",
            "provider": "test_provider"
        }
        
        service.save_tool(tool_data)
        
        # Verify session operations
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch('core.catalog.database_service.create_engine')
    @patch('core.catalog.database_service.sessionmaker')
    def test_save_trigger(self, mock_sessionmaker, mock_engine):
        """Test saving a trigger to database."""
        mock_session = Mock()
        mock_sessionmaker.return_value = mock_session
        
        service = CatalogDatabaseService(database_url="sqlite:///:memory:")
        
        trigger_data = {
            "id": "trigger_123",
            "name": "Test Trigger",
            "description": "A test trigger",
            "category": "test",
            "provider": "test_provider"
        }
        
        service.save_trigger(trigger_data)
        
        # Verify session operations
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch('core.catalog.database_service.create_engine')
    @patch('core.catalog.database_service.sessionmaker')
    def test_get_tool(self, mock_sessionmaker, mock_engine):
        """Test getting a tool from database."""
        mock_session = Mock()
        mock_sessionmaker.return_value = mock_session
        
        # Mock tool query result
        mock_tool = Mock()
        mock_tool.id = "tool_123"
        mock_tool.name = "Test Tool"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_tool
        
        service = CatalogDatabaseService(database_url="sqlite:///:memory:")
        
        result = service.get_tool("tool_123")
        
        assert result.id == "tool_123"
        assert result.name == "Test Tool"

    @patch('core.catalog.database_service.create_engine')
    @patch('core.catalog.database_service.sessionmaker')
    def test_get_trigger(self, mock_sessionmaker, mock_engine):
        """Test getting a trigger from database."""
        mock_session = Mock()
        mock_sessionmaker.return_value = mock_session
        
        # Mock trigger query result
        mock_trigger = Mock()
        mock_trigger.id = "trigger_123"
        mock_trigger.name = "Test Trigger"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_trigger
        
        service = CatalogDatabaseService(database_url="sqlite:///:memory:")
        
        result = service.get_trigger("trigger_123")
        
        assert result.id == "trigger_123"
        assert result.name == "Test Trigger"

    @patch('core.catalog.database_service.create_engine')
    @patch('core.catalog.database_service.sessionmaker')
    def test_list_tools(self, mock_sessionmaker, mock_engine):
        """Test listing tools from database."""
        mock_session = Mock()
        mock_sessionmaker.return_value = mock_session
        
        # Mock tools query result
        mock_tools = [
            Mock(id="tool_1", name="Tool 1"),
            Mock(id="tool_2", name="Tool 2")
        ]
        mock_session.query.return_value.all.return_value = mock_tools
        
        service = CatalogDatabaseService(database_url="sqlite:///:memory:")
        
        result = service.list_tools()
        
        assert len(result) == 2
        assert result[0].id == "tool_1"
        assert result[1].id == "tool_2"

    @patch('core.catalog.database_service.create_engine')
    @patch('core.catalog.database_service.sessionmaker')
    def test_list_triggers(self, mock_sessionmaker, mock_engine):
        """Test listing triggers from database."""
        mock_session = Mock()
        mock_sessionmaker.return_value = mock_session
        
        # Mock triggers query result
        mock_triggers = [
            Mock(id="trigger_1", name="Trigger 1"),
            Mock(id="trigger_2", name="Trigger 2")
        ]
        mock_session.query.return_value.all.return_value = mock_triggers
        
        service = CatalogDatabaseService(database_url="sqlite:///:memory:")
        
        result = service.list_triggers()
        
        assert len(result) == 2
        assert result[0].id == "trigger_1"
        assert result[1].id == "trigger_2"


class TestComposioCatalogClient:
    """Test the ComposioCatalogClient class."""
    
    def test_client_initialization(self):
        """Test ComposioCatalogClient initialization."""
        with patch('core.catalog.composio_client.httpx.AsyncClient') as mock_client:
            client = ComposioCatalogClient(
                api_key="test_key",
                base_url="https://api.composio.dev"
            )
            
            assert client.api_key == "test_key"
            assert client.base_url == "https://api.composio.dev"
            assert client.headers["Authorization"] == "Bearer test_key"

    @patch('core.catalog.composio_client.httpx.AsyncClient')
    async def test_fetch_tools(self, mock_client):
        """Test fetching tools from Composio."""
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tools": [
                {"id": "tool_1", "name": "Tool 1"},
                {"id": "tool_2", "name": "Tool 2"}
            ]
        }
        mock_client_instance.get.return_value = mock_response
        
        client = ComposioCatalogClient(
            api_key="test_key",
            base_url="https://api.composio.dev"
        )
        
        result = await client.fetch_tools()
        
        assert len(result) == 2
        assert result[0]["id"] == "tool_1"
        assert result[1]["id"] == "tool_2"

    @patch('core.catalog.composio_client.httpx.AsyncClient')
    async def test_fetch_triggers(self, mock_client):
        """Test fetching triggers from Composio."""
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "triggers": [
                {"id": "trigger_1", "name": "Trigger 1"},
                {"id": "trigger_2", "name": "Trigger 2"}
            ]
        }
        mock_client_instance.get.return_value = mock_response
        
        client = ComposioCatalogClient(
            api_key="test_key",
            base_url="https://api.composio.dev"
        )
        
        result = await client.fetch_triggers()
        
        assert len(result) == 2
        assert result[0]["id"] == "trigger_1"
        assert result[1]["id"] == "trigger_2"

    @patch('core.catalog.composio_client.httpx.AsyncClient')
    async def test_fetch_categories(self, mock_client):
        """Test fetching categories from Composio."""
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "categories": [
                {"id": "cat_1", "name": "Category 1"},
                {"id": "cat_2", "name": "Category 2"}
            ]
        }
        mock_client_instance.get.return_value = mock_response
        
        client = ComposioCatalogClient(
            api_key="test_key",
            base_url="https://api.composio.dev"
        )
        
        result = await client.fetch_categories()
        
        assert len(result) == 2
        assert result[0]["id"] == "cat_1"
        assert result[1]["id"] == "cat_2"

    @patch('core.catalog.composio_client.httpx.AsyncClient')
    async def test_fetch_tool_details(self, mock_client):
        """Test fetching tool details from Composio."""
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "tool_123",
            "name": "Test Tool",
            "description": "A test tool",
            "inputs": {"param1": "string"},
            "outputs": {"result": "string"}
        }
        mock_client_instance.get.return_value = mock_response
        
        client = ComposioCatalogClient(
            api_key="test_key",
            base_url="https://api.composio.dev"
        )
        
        result = await client.fetch_tool_details("tool_123")
        
        assert result["id"] == "tool_123"
        assert result["name"] == "Test Tool"
        assert "inputs" in result
        assert "outputs" in result

    @patch('core.catalog.composio_client.httpx.AsyncClient')
    async def test_fetch_trigger_details(self, mock_client):
        """Test fetching trigger details from Composio."""
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "trigger_123",
            "name": "Test Trigger",
            "description": "A test trigger",
            "payload_schema": {"event": "object"}
        }
        mock_client_instance.get.return_value = mock_response
        
        client = ComposioCatalogClient(
            api_key="test_key",
            base_url="https://api.composio.dev"
        )
        
        result = await client.fetch_trigger_details("trigger_123")
        
        assert result["id"] == "trigger_123"
        assert result["name"] == "Test Trigger"
        assert "payload_schema" in result

    @patch('core.catalog.composio_client.httpx.AsyncClient')
    async def test_error_handling(self, mock_client):
        """Test error handling in API calls."""
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client_instance.get.return_value = mock_response
        
        client = ComposioCatalogClient(
            api_key="test_key",
            base_url="https://api.composio.dev"
        )
        
        with pytest.raises(Exception):
            await client.fetch_tools()

    @patch('core.catalog.composio_client.httpx.AsyncClient')
    async def test_timeout_handling(self, mock_client):
        """Test timeout handling in API calls."""
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock timeout
        mock_client_instance.get.side_effect = asyncio.TimeoutError()
        
        client = ComposioCatalogClient(
            api_key="test_key",
            base_url="https://api.composio.dev"
        )
        
        with pytest.raises(asyncio.TimeoutError):
            await client.fetch_tools()

    def test_url_building(self):
        """Test URL building for different endpoints."""
        client = ComposioCatalogClient(
            api_key="test_key",
            base_url="https://api.composio.dev"
        )
        
        # Test tools endpoint
        tools_url = client._build_url("/tools")
        assert tools_url == "https://api.composio.dev/tools"
        
        # Test triggers endpoint
        triggers_url = client._build_url("/triggers")
        assert triggers_url == "https://api.composio.dev/triggers"
        
        # Test categories endpoint
        categories_url = client._build_url("/categories")
        assert categories_url == "https://api.composio.dev/categories"

    def test_headers_construction(self):
        """Test that appropriate headers are set."""
        client = ComposioCatalogClient(
            api_key="test_key",
            base_url="https://api.composio.dev"
        )
        
        headers = client._get_headers()
        
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_key"
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"
        assert "User-Agent" in headers
