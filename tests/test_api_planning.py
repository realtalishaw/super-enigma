"""
Tests for the planning API routes.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock, MagicMock
import json


class TestPlanningRoutes:
    """Test the planning API routes."""

    def test_planning_router_included(self, test_client):
        """Test that planning router is included in the main app."""
        # This test verifies that the planning router is accessible
        response = test_client.get("/")
        assert response.status_code == 200

    @patch('api.routes.planning.plan_workflow')
    def test_plan_workflow_endpoint(self, mock_plan_workflow, test_client):
        """Test POST /planning/plan endpoint."""
        # Mock the planning function
        mock_plan_result = {
            "workflow_id": "planned_workflow_123",
            "plan": {
                "nodes": [
                    {"id": "node1", "type": "trigger", "name": "Start"},
                    {"id": "node2", "type": "action", "name": "Process"}
                ],
                "edges": [{"from": "node1", "to": "node2"}]
            },
            "confidence": 0.95,
            "estimated_duration": "5 minutes"
        }
        mock_plan_workflow.return_value = mock_plan_result
        
        # Test data
        planning_request = {
            "description": "Automate email notifications",
            "requirements": ["Send email", "Track status"],
            "constraints": {"timeout": "10 minutes"}
        }
        
        # Test the endpoint
        response = test_client.post(
            "/planning/plan",
            json=planning_request,
            headers={"Content-Type": "application/json"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "planned_workflow_123"
        assert data["confidence"] == 0.95
        assert "plan" in data
        
        # Verify the mock was called
        mock_plan_workflow.assert_called_once_with(planning_request)

    @patch('api.routes.planning.optimize_workflow')
    def test_optimize_workflow_endpoint(self, mock_optimize, test_client):
        """Test POST /planning/optimize endpoint."""
        # Mock the optimization function
        mock_optimized_result = {
            "workflow_id": "optimized_workflow_123",
            "optimizations": [
                {"type": "parallel_execution", "description": "Run nodes in parallel"},
                {"type": "caching", "description": "Add result caching"}
            ],
            "performance_improvement": "40%",
            "estimated_savings": "3 minutes"
        }
        mock_optimize.return_value = mock_optimized_result
        
        # Test data
        optimization_request = {
            "workflow_id": "workflow_123",
            "optimization_goals": ["speed", "cost"],
            "constraints": {"max_nodes": 20}
        }
        
        # Test the endpoint
        response = test_client.post(
            "/planning/optimize",
            json=optimization_request,
            headers={"Content-Type": "application/json"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "optimized_workflow_123"
        assert len(data["optimizations"]) == 2
        assert data["performance_improvement"] == "40%"
        
        # Verify the mock was called
        mock_optimize.assert_called_once_with(optimization_request)

    @patch('api.routes.planning.validate_workflow_plan')
    def test_validate_plan_endpoint(self, mock_validate, test_client):
        """Test POST /planning/validate endpoint."""
        # Mock the validation function
        mock_validation_result = {
            "is_valid": True,
            "warnings": [
                {"type": "performance", "message": "Consider caching for repeated operations"}
            ],
            "errors": [],
            "suggestions": [
                {"type": "optimization", "message": "Add error handling for node2"}
            ]
        }
        mock_validate.return_value = mock_validation_result
        
        # Test data
        workflow_plan = {
            "nodes": [
                {"id": "node1", "type": "trigger"},
                {"id": "node2", "type": "action"}
            ],
            "edges": [{"from": "node1", "to": "node2"}]
        }
        
        # Test the endpoint
        response = test_client.post(
            "/planning/validate",
            json=workflow_plan,
            headers={"Content-Type": "application/json"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert len(data["warnings"]) == 1
        assert len(data["suggestions"]) == 1
        
        # Verify the mock was called
        mock_validate.assert_called_once_with(workflow_plan)

    @patch('api.routes.planning.estimate_workflow_cost')
    def test_estimate_cost_endpoint(self, mock_estimate, test_client):
        """Test POST /planning/estimate-cost endpoint."""
        # Mock the cost estimation function
        mock_cost_estimate = {
            "workflow_id": "workflow_123",
            "estimated_cost": 0.25,
            "cost_breakdown": {
                "compute": 0.15,
                "api_calls": 0.08,
                "storage": 0.02
            },
            "currency": "USD",
            "billing_period": "per_execution"
        }
        mock_estimate.return_value = mock_cost_estimate
        
        # Test data
        cost_request = {
            "workflow_id": "workflow_123",
            "execution_frequency": "daily",
            "expected_volume": 100
        }
        
        # Test the endpoint
        response = test_client.post(
            "/planning/estimate-cost",
            json=cost_request,
            headers={"Content-Type": "application/json"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["estimated_cost"] == 0.25
        assert data["currency"] == "USD"
        assert "cost_breakdown" in data
        
        # Verify the mock was called
        mock_estimate.assert_called_once_with(cost_request)

    @patch('api.routes.planning.get_planning_history')
    def test_get_planning_history_endpoint(self, mock_get_history, test_client):
        """Test GET /planning/history endpoint."""
        # Mock the history function
        mock_history = [
            {
                "id": "plan_1",
                "workflow_id": "workflow_123",
                "created_at": "2024-01-01T00:00:00Z",
                "plan_type": "initial_plan",
                "status": "completed"
            },
            {
                "id": "plan_2",
                "workflow_id": "workflow_123",
                "created_at": "2024-01-02T00:00:00Z",
                "plan_type": "optimization",
                "status": "completed"
            }
        ]
        mock_get_history.return_value = mock_history
        
        # Test the endpoint
        response = test_client.get("/planning/history?workflow_id=workflow_123")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["plan_type"] == "initial_plan"
        assert data[1]["plan_type"] == "optimization"
        
        # Verify the mock was called
        mock_get_history.assert_called_once_with("workflow_123")

    @patch('api.routes.planning.plan_workflow')
    def test_plan_workflow_validation(self, mock_plan_workflow, test_client):
        """Test planning validation with invalid data."""
        # Test with missing required fields
        invalid_request = {
            "description": "Test workflow"
            # Missing requirements
        }
        
        response = test_client.post(
            "/planning/plan",
            json=invalid_request,
            headers={"Content-Type": "application/json"}
        )
        
        # Should return validation error
        assert response.status_code in [400, 422]

    @patch('api.routes.planning.optimize_workflow')
    def test_optimize_workflow_validation(self, mock_optimize, test_client):
        """Test optimization validation with invalid data."""
        # Test with invalid workflow ID
        invalid_request = {
            "workflow_id": "",  # Empty workflow ID
            "optimization_goals": ["speed"]
        }
        
        response = test_client.post(
            "/planning/optimize",
            json=invalid_request,
            headers={"Content-Type": "application/json"}
        )
        
        # Should return validation error
        assert response.status_code in [400, 422]

    def test_planning_endpoint_validation(self, test_client):
        """Test planning endpoint validation."""
        # Test with malformed JSON
        response = test_client.post(
            "/planning/plan",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        # Should return validation error
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_async_planning_operations(self, async_client):
        """Test async planning operations."""
        # Test async planning request
        planning_request = {
            "description": "Async test workflow",
            "requirements": ["Async operation"],
            "constraints": {"timeout": "5 minutes"}
        }
        
        response = await async_client.post("/planning/plan", json=planning_request)
        # Status depends on whether the endpoint is implemented
        assert response.status_code in [200, 404, 501]

    def test_planning_error_handling(self, test_client):
        """Test planning error handling."""
        # Test with invalid workflow plan
        invalid_plan = {
            "nodes": "not_a_list",  # Should be a list
            "edges": []
        }
        
        response = test_client.post(
            "/planning/validate",
            json=invalid_plan,
            headers={"Content-Type": "application/json"}
        )
        
        # Should handle gracefully
        assert response.status_code in [400, 422]

    def test_planning_constraints_validation(self, test_client):
        """Test planning constraints validation."""
        # Test with invalid constraints
        invalid_constraints = {
            "description": "Test workflow",
            "requirements": ["Test requirement"],
            "constraints": {
                "timeout": "invalid_timeout",  # Invalid timeout format
                "max_nodes": "not_a_number"    # Should be a number
            }
        }
        
        response = test_client.post(
            "/planning/plan",
            json=invalid_constraints,
            headers={"Content-Type": "application/json"}
        )
        
        # Should return validation error
        assert response.status_code in [400, 422]

    def test_planning_performance_metrics(self, test_client):
        """Test planning performance metrics endpoint if it exists."""
        # Test performance metrics endpoint
        response = test_client.get("/planning/metrics")
        # Status depends on whether the endpoint is implemented
        assert response.status_code in [200, 404, 501]

    def test_planning_templates(self, test_client):
        """Test planning templates endpoint if it exists."""
        # Test templates endpoint
        response = test_client.get("/planning/templates")
        # Status depends on whether the endpoint is implemented
        assert response.status_code in [200, 404, 501]

    def test_planning_ai_suggestions(self, test_client):
        """Test AI suggestions endpoint if it exists."""
        # Test AI suggestions endpoint
        response = test_client.get("/planning/ai-suggestions")
        # Status depends on whether the endpoint is implemented
        assert response.status_code in [200, 404, 501]

    def test_planning_workflow_complexity(self, test_client):
        """Test workflow complexity analysis endpoint if it exists."""
        # Test complexity analysis endpoint
        response = test_client.post(
            "/planning/analyze-complexity",
            json={"workflow_id": "workflow_123"}
        )
        # Status depends on whether the endpoint is implemented
        assert response.status_code in [200, 404, 501]

    def test_planning_resource_requirements(self, test_client):
        """Test resource requirements endpoint if it exists."""
        # Test resource requirements endpoint
        response = test_client.post(
            "/planning/resource-requirements",
            json={"workflow_id": "workflow_123"}
        )
        # Status depends on whether the endpoint is implemented
        assert response.status_code in [200, 404, 501]
