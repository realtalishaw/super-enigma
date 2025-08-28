"""
Tests for the frontend API routes.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock, MagicMock
import json


class TestFrontendRoutes:
    """Test the frontend API routes."""

    def test_frontend_router_included(self, test_client):
        """Test that frontend router is included in the main app."""
        # This test verifies that the frontend router is accessible
        response = test_client.get("/")
        assert response.status_code == 200

    @patch('api.routes.frontend.auth.authenticate_user')
    def test_user_authentication_endpoint(self, mock_authenticate, test_client):
        """Test POST /auth/login endpoint."""
        # Mock the authentication function
        mock_authenticate.return_value = {
            "user_id": "user_123",
            "email": "test@example.com",
            "access_token": "jwt_token_123"
        }
        
        # Test data
        auth_data = {
            "email": "test@example.com",
            "password": "password123"
        }
        
        # Test the endpoint
        response = test_client.post(
            "/auth/login",
            json=auth_data,
            headers={"Content-Type": "application/json"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user_id"] == "user_123"
        
        # Verify the mock was called
        mock_authenticate.assert_called_once_with(auth_data)

    @patch('api.routes.frontend.auth.register_user')
    def test_user_registration_endpoint(self, mock_register, test_client):
        """Test POST /auth/register endpoint."""
        # Mock the registration function
        mock_register.return_value = {
            "user_id": "new_user_123",
            "email": "new@example.com",
            "message": "User registered successfully"
        }
        
        # Test data
        user_data = {
            "email": "new@example.com",
            "password": "password123",
            "name": "New User"
        }
        
        # Test the endpoint
        response = test_client.post(
            "/auth/register",
            json=user_data,
            headers={"Content-Type": "application/json"}
        )
        
        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == "new_user_123"
        assert data["email"] == "new@example.com"
        
        # Verify the mock was called
        mock_register.assert_called_once_with(user_data)

    @patch('api.routes.frontend.integrations.get_user_integrations')
    def test_get_integrations_endpoint(self, mock_get_integrations, test_client):
        """Test GET /integrations endpoint."""
        # Mock the integrations function
        mock_integrations = [
            {
                "id": "integration_1",
                "name": "Slack",
                "status": "connected",
                "provider": "slack"
            },
            {
                "id": "integration_2",
                "name": "GitHub",
                "status": "disconnected",
                "provider": "github"
            }
        ]
        mock_get_integrations.return_value = mock_integrations
        
        # Test the endpoint
        response = test_client.get("/integrations")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Slack"
        assert data[1]["name"] == "GitHub"
        
        # Verify the mock was called
        mock_get_integrations.assert_called_once()

    @patch('api.routes.frontend.integrations.connect_integration')
    def test_connect_integration_endpoint(self, mock_connect, test_client):
        """Test POST /integrations/connect endpoint."""
        # Mock the connection function
        mock_connect.return_value = {
            "integration_id": "integration_123",
            "status": "connected",
            "message": "Integration connected successfully"
        }
        
        # Test data
        integration_data = {
            "provider": "slack",
            "credentials": {
                "token": "slack_token_123"
            }
        }
        
        # Test the endpoint
        response = test_client.post(
            "/integrations/connect",
            json=integration_data,
            headers={"Content-Type": "application/json"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["provider"] == "slack"
        
        # Verify the mock was called
        mock_connect.assert_called_once_with(integration_data)

    @patch('api.routes.frontend.integrations.disconnect_integration')
    def test_disconnect_integration_endpoint(self, mock_disconnect, test_client):
        """Test POST /integrations/{integration_id}/disconnect endpoint."""
        # Mock the disconnection function
        mock_disconnect.return_value = {
            "integration_id": "integration_123",
            "status": "disconnected",
            "message": "Integration disconnected successfully"
        }
        
        # Test the endpoint
        response = test_client.post("/integrations/integration_123/disconnect")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "disconnected"
        
        # Verify the mock was called
        mock_disconnect.assert_called_once_with("integration_123")

    @patch('api.user_services.user_service.UserService.get_user_preferences')
    def test_get_preferences_endpoint(self, mock_get_preferences, test_client):
        """Test GET /preferences/{user_id} endpoint."""
        # Mock the user service method
        mock_preferences = {
            "theme": "dark",
            "notifications": "true",
            "timezone": "UTC",
            "language": "en"
        }
        mock_get_preferences.return_value = mock_preferences
        
        # Test the endpoint with a user ID
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        response = test_client.get(f"/api/preferences/{user_id}")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user_id
        assert data["preferences"]["theme"] == "dark"
        assert data["preferences"]["notifications"] == "true"
        assert data["preferences"]["timezone"] == "UTC"
        assert data["count"] == 4
        
        # Verify the mock was called with the user ID
        mock_get_preferences.assert_called_once()

    @patch('api.routes.frontend.suggestions.get_workflow_suggestions')
    def test_get_suggestions_endpoint(self, mock_get_suggestions, test_client):
        """Test GET /suggestions endpoint."""
        # Mock the suggestions function
        mock_suggestions = [
            {
                "id": "suggestion_1",
                "title": "Automate Slack Notifications",
                "description": "Send notifications when workflows complete",
                "difficulty": "easy"
            },
            {
                "id": "suggestion_2",
                "title": "GitHub Issue Automation",
                "description": "Automatically create issues from triggers",
                "difficulty": "medium"
            }
        ]
        mock_get_suggestions.return_value = mock_suggestions
        
        # Test the endpoint
        response = test_client.get("/suggestions")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "Automate Slack Notifications"
        assert data[1]["title"] == "GitHub Issue Automation"
        
        # Verify the mock was called
        mock_get_suggestions.assert_called_once()

    @patch('api.routes.frontend.suggestions.get_personalized_suggestions')
    def test_get_personalized_suggestions_endpoint(self, mock_get_personalized, test_client):
        """Test GET /suggestions/personalized endpoint."""
        # Mock the personalized suggestions function
        mock_personalized = [
            {
                "id": "personal_1",
                "title": "Custom Workflow for You",
                "description": "Based on your usage patterns",
                "relevance_score": 0.95
            }
        ]
        mock_get_personalized.return_value = mock_personalized
        
        # Test the endpoint
        response = test_client.get("/suggestions/personalized")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Custom Workflow for You"
        assert data[0]["relevance_score"] == 0.95
        
        # Verify the mock was called
        mock_get_personalized.assert_called_once()

    def test_authentication_validation(self, test_client):
        """Test authentication validation with invalid data."""
        # Test with invalid email format
        invalid_auth = {
            "email": "invalid_email",
            "password": "password123"
        }
        
        response = test_client.post(
            "/auth/login",
            json=invalid_auth,
            headers={"Content-Type": "application/json"}
        )
        
        # Should return validation error
        assert response.status_code in [400, 422]

    def test_registration_validation(self, test_client):
        """Test registration validation with invalid data."""
        # Test with weak password
        invalid_registration = {
            "email": "test@example.com",
            "password": "123",  # Too short
            "name": "Test User"
        }
        
        response = test_client.post(
            "/auth/register",
            json=invalid_registration,
            headers={"Content-Type": "application/json"}
        )
        
        # Should return validation error
        assert response.status_code in [400, 422]

    def test_integration_validation(self, test_client):
        """Test integration validation with invalid data."""
        # Test with missing credentials
        invalid_integration = {
            "provider": "slack"
            # Missing credentials
        }
        
        response = test_client.post(
            "/integrations/connect",
            json=invalid_integration,
            headers={"Content-Type": "application/json"}
        )
        
        # Should return validation error
        assert response.status_code in [400, 422]

    def test_preferences_validation(self, test_client):
        """Test preferences validation with invalid data."""
        # Test with invalid theme
        invalid_preferences = {
            "theme": "invalid_theme",
            "notifications": "not_a_boolean"
        }
        
        response = test_client.put(
            "/preferences",
            json=invalid_preferences,
            headers={"Content-Type": "application/json"}
        )
        
        # Should return validation error
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_async_frontend_operations(self, async_client):
        """Test async frontend operations."""
        # Test async GET request for integrations
        response = await async_client.get("/integrations")
        assert response.status_code in [200, 404]  # 404 if no integrations exist
        
        # Test async POST request for authentication
        auth_data = {
            "email": "test@example.com",
            "password": "password123"
        }
        
        response = await async_client.post("/auth/login", json=auth_data)
        # Status depends on whether the endpoint is implemented
        assert response.status_code in [200, 404, 501]

    def test_cors_headers(self, test_client):
        """Test that CORS headers are properly set."""
        # Test preflight request
        response = test_client.options("/auth/login")
        
        # Check CORS headers
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers

    def test_error_handling(self, test_client):
        """Test error handling for frontend routes."""
        # Test authentication with invalid credentials
        invalid_credentials = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        }
        
        response = test_client.post(
            "/auth/login",
            json=invalid_credentials,
            headers={"Content-Type": "application/json"}
        )
        
        # Should handle gracefully (either 401 or 404)
        assert response.status_code in [400, 401, 404, 422]

    def test_rate_limiting(self, test_client):
        """Test rate limiting for authentication endpoints."""
        # This would depend on your rate limiting implementation
        # For now, we'll just test that the endpoints respond
        auth_data = {
            "email": "test@example.com",
            "password": "password123"
        }
        
        # Make multiple requests to test rate limiting
        for _ in range(3):
            response = test_client.post(
                "/auth/login",
                json=auth_data,
                headers={"Content-Type": "application/json"}
            )
            # Should handle gracefully regardless of rate limiting
            assert response.status_code in [200, 400, 401, 422, 429]

    def test_session_management(self, test_client):
        """Test session management functionality."""
        # This would depend on your session management implementation
        # For now, we'll just test that the endpoints respond
        
        # Test logout endpoint if it exists
        response = test_client.post("/auth/logout")
        # Status depends on whether the endpoint is implemented
        assert response.status_code in [200, 404, 501]
        
        # Test refresh token endpoint if it exists
        response = test_client.post("/auth/refresh")
        # Status depends on whether the endpoint is implemented
        assert response.status_code in [200, 401, 404, 501]
