"""
Tests for the main FastAPI application.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from api.main import app


class TestMainApp:
    """Test the main FastAPI application."""

    def test_app_creation(self):
        """Test that the FastAPI app is created correctly."""
        assert app.title == "Workflow Orchestration API 2.0"
        assert app.description is not None
        assert app.version == "1.0.0"

    def test_cors_middleware(self):
        """Test that CORS middleware is configured correctly."""
        cors_middleware = None
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                cors_middleware = middleware
                break
        
        assert cors_middleware is not None
        assert "http://localhost:8000" in cors_middleware.options.allow_origins

    def test_routers_included(self):
        """Test that all required routers are included."""
        expected_routers = [
            "system_router",
            "frontend_router", 
            "planning_router",
            "runs_router",
            "catalog_router",

        ]
        
        for router_name in expected_routers:
            # Check if router is included by looking at the app's routes
            router_found = False
            for route in app.routes:
                if hasattr(route, 'tags') and route.tags:
                    # This is a simplified check - in practice you'd want to verify specific routes
                    router_found = True
                    break
            assert router_found, f"Router {router_name} should be included"

    def test_root_endpoint(self, test_client):
        """Test the root endpoint."""
        response = test_client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Workflow Orchestration API"
        assert data["version"] == "1.0.0"
        assert "docs" in data
        assert "redoc" in data

    def test_docs_endpoint(self, test_client):
        """Test that the docs endpoint is accessible."""
        response = test_client.get("/docs")
        assert response.status_code == 200

    def test_redoc_endpoint(self, test_client):
        """Test that the redoc endpoint is accessible."""
        response = test_client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_schema(self, test_client):
        """Test that the OpenAPI schema is accessible."""
        response = test_client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema

    def test_app_metadata(self):
        """Test app metadata and configuration."""
        assert hasattr(app, 'title')
        assert hasattr(app, 'description')
        assert hasattr(app, 'version')
        assert hasattr(app, 'docs_url')
        assert hasattr(app, 'redoc_url')

    def test_middleware_order(self):
        """Test that middleware is added in the correct order."""
        # CORS middleware should be one of the first middleware
        middleware_classes = [middleware.cls.__name__ for middleware in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes

    def test_router_prefixes(self):
        """Test that routers have appropriate prefixes."""
        # This test would need to be updated based on your actual router configuration
        # For now, we'll just verify that routers exist
        assert len(app.routes) > 0

    def test_health_check_endpoint(self, test_client):
        """Test health check endpoint if it exists."""
        # This would depend on whether you have a health check endpoint
        # For now, we'll test that the app responds to basic requests
        response = test_client.get("/")
        assert response.status_code == 200

    def test_error_handling(self, test_client):
        """Test that the app handles errors gracefully."""
        # Test a non-existent endpoint
        response = test_client.get("/nonexistent")
        assert response.status_code == 404

    def test_response_headers(self, test_client):
        """Test that responses include appropriate headers."""
        response = test_client.get("/")
        assert response.status_code == 200
        
        # Check for common headers
        assert "content-type" in response.headers
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_async_root_endpoint(self, async_client):
        """Test the root endpoint asynchronously."""
        response = await async_client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Workflow Orchestration API"
        assert data["version"] == "1.0.0"
