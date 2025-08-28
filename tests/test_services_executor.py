"""
Tests for the executor service.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio
from datetime import datetime
from services.executor.executor import (
    WorkflowExecutor,
    ComposioClient,
    StateStore,
    IdempotencyCache,
    ExecutionContext,
    NodeExecution,
    WorkflowRun,
    NodeType,
    NodeStatus,
    RunStatus
)


class TestNodeType:
    """Test the NodeType enum."""
    
    def test_node_type_values(self):
        """Test that NodeType has expected values."""
        assert NodeType.TRIGGER == "trigger"
        assert NodeType.ACTION == "action"
        assert NodeType.GATEWAY_IF == "gateway_if"
        assert NodeType.GATEWAY_SWITCH == "gateway_switch"
        assert NodeType.PARALLEL == "parallel"
        assert NodeType.JOIN == "join"
        assert NodeType.LOOP_WHILE == "loop_while"
        assert NodeType.LOOP_FOREACH == "loop_foreach"


class TestNodeStatus:
    """Test the NodeStatus enum."""
    
    def test_node_status_values(self):
        """Test that NodeStatus has expected values."""
        assert NodeStatus.PENDING == "PENDING"
        assert NodeStatus.RUNNING == "RUNNING"
        assert NodeStatus.DONE == "DONE"
        assert NodeStatus.ERROR == "ERROR"
        assert NodeStatus.SKIPPED == "SKIPPED"


class TestRunStatus:
    """Test the RunStatus enum."""
    
    def test_run_status_values(self):
        """Test that RunStatus has expected values."""
        assert RunStatus.RUNNING == "RUNNING"
        assert RunStatus.SUCCESS == "SUCCESS"
        assert RunStatus.FAILED == "FAILED"


class TestComposioClient:
    """Test the ComposioClient class."""
    
    def test_composio_client_initialization(self):
        """Test ComposioClient initialization."""
        with patch('services.executor.executor.requests') as mock_requests:
            client = ComposioClient(api_key="test_key", base_url="https://test.com")
            
            assert client.api_key == "test_key"
            assert client.base_url == "https://test.com"
            assert client.headers["Authorization"] == "Bearer test_key"

    @patch('services.executor.executor.requests.get')
    def test_fetch_tool(self, mock_get):
        """Test fetching a tool from Composio."""
        mock_response = Mock()
        mock_response.json.return_value = {"tool": "test_tool"}
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        with patch('services.executor.executor.requests'):
            client = ComposioClient(api_key="test_key", base_url="https://test.com")
            result = client.fetch_tool("tool_id")
            
            assert result == {"tool": "test_tool"}
            mock_get.assert_called_once()

    @patch('services.executor.executor.requests.get')
    def test_fetch_tool_error(self, mock_get):
        """Test error handling when fetching a tool."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with patch('services.executor.executor.requests'):
            client = ComposioClient(api_key="test_key", base_url="https://test.com")
            
            with pytest.raises(Exception):
                client.fetch_tool("nonexistent_tool")


class TestStateStore:
    """Test the StateStore class."""
    
    def test_state_store_initialization(self):
        """Test StateStore initialization."""
        with patch('services.executor.executor.redis.Redis') as mock_redis:
            store = StateStore(redis_url="redis://localhost:6379")
            
            assert store.redis_url == "redis://localhost:6379"
            mock_redis.assert_called_once()

    @patch('services.executor.executor.redis.Redis')
    def test_save_state(self, mock_redis):
        """Test saving state."""
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        
        store = StateStore(redis_url="redis://localhost:6379")
        store.save_state("key", {"data": "value"})
        
        mock_redis_instance.set.assert_called_once()

    @patch('services.executor.executor.redis.Redis')
    def test_get_state(self, mock_redis):
        """Test getting state."""
        mock_redis_instance = Mock()
        mock_redis_instance.get.return_value = '{"data": "value"}'
        mock_redis.return_value = mock_redis_instance
        
        store = StateStore(redis_url="redis://localhost:6379")
        result = store.get_state("key")
        
        assert result == {"data": "value"}
        mock_redis_instance.get.assert_called_once_with("key")


class TestIdempotencyCache:
    """Test the IdempotencyCache class."""
    
    def test_idempotency_cache_initialization(self):
        """Test IdempotencyCache initialization."""
        with patch('services.executor.executor.redis.Redis') as mock_redis:
            cache = IdempotencyCache(redis_url="redis://localhost:6379")
            
            assert cache.redis_url == "redis://localhost:6379"
            mock_redis.assert_called_once()

    @patch('services.executor.executor.redis.Redis')
    def test_check_idempotency(self, mock_redis):
        """Test checking idempotency."""
        mock_redis_instance = Mock()
        mock_redis_instance.exists.return_value = True
        mock_redis.return_value = mock_redis_instance
        
        cache = IdempotencyCache(redis_url="redis://localhost:6379")
        result = cache.check_idempotency("key")
        
        assert result is True
        mock_redis_instance.exists.assert_called_once_with("key")

    @patch('services.executor.executor.redis.Redis')
    def test_set_idempotency(self, mock_redis):
        """Test setting idempotency key."""
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        
        cache = IdempotencyCache(redis_url="redis://localhost:6379")
        cache.set_idempotency("key", "value", ttl=300)
        
        mock_redis_instance.setex.assert_called_once_with("key", 300, "value")


class TestExecutionContext:
    """Test the ExecutionContext class."""
    
    def test_execution_context_initialization(self):
        """Test ExecutionContext initialization."""
        context = ExecutionContext(
            workflow_id="workflow_123",
            run_id="run_456",
            input_data={"test": "data"},
            metadata={"user_id": "user_123"}
        )
        
        assert context.workflow_id == "workflow_123"
        assert context.run_id == "run_456"
        assert context.input_data == {"test": "data"}
        assert context.metadata == {"user_id": "user_123"}
        assert context.start_time is not None

    def test_execution_context_timing(self):
        """Test execution context timing functionality."""
        context = ExecutionContext(
            workflow_id="workflow_123",
            run_id="run_456"
        )
        
        # Test start time
        assert context.start_time is not None
        
        # Test duration calculation
        import time
        time.sleep(0.1)  # Small delay
        
        duration = context.get_duration()
        assert duration > 0


class TestNodeExecution:
    """Test the NodeExecution class."""
    
    def test_node_execution_initialization(self):
        """Test NodeExecution initialization."""
        execution = NodeExecution(
            run_id="run_123",
            node_id="node_123",
            status=NodeStatus.PENDING
        )
        
        assert execution.run_id == "run_123"
        assert execution.node_id == "node_123"
        assert execution.status == NodeStatus.PENDING
        assert execution.attempt == 0
        assert execution.output is None
        assert execution.error is None
        assert execution.started_at is None
        assert execution.finished_at is None
        assert execution.from_cache is False

    def test_node_execution_lifecycle(self):
        """Test NodeExecution lifecycle methods."""
        execution = NodeExecution(
            run_id="run_123",
            node_id="node_123",
            status=NodeStatus.PENDING
        )
        
        # Test status updates
        execution.status = NodeStatus.RUNNING
        execution.started_at = datetime.now()
        assert execution.status == NodeStatus.RUNNING
        assert execution.started_at is not None
        
        # Test completion
        execution.status = NodeStatus.DONE
        execution.output = {"result": "success"}
        execution.finished_at = datetime.now()
        assert execution.status == NodeStatus.DONE
        assert execution.output == {"result": "success"}
        assert execution.finished_at is not None

    def test_node_execution_failure(self):
        """Test NodeExecution failure handling."""
        execution = NodeExecution(
            run_id="run_123",
            node_id="node_123",
            status=NodeStatus.PENDING
        )
        
        execution.status = NodeStatus.ERROR
        execution.error = "Test error"
        execution.finished_at = datetime.now()
        
        assert execution.status == NodeStatus.ERROR
        assert execution.error == "Test error"
        assert execution.finished_at is not None


class TestWorkflowRun:
    """Test the WorkflowRun class."""
    
    def test_workflow_run_initialization(self):
        """Test WorkflowRun initialization."""
        run = WorkflowRun(
            run_id="run_123",
            workflow_id="workflow_456",
            version="1.0",
            user_id="user_123",
            status=RunStatus.RUNNING,
            started_at=datetime.now()
        )
        
        assert run.run_id == "run_123"
        assert run.workflow_id == "workflow_456"
        assert run.version == "1.0"
        assert run.user_id == "user_123"
        assert run.status == RunStatus.RUNNING
        assert run.started_at is not None
        assert run.finished_at is None
        assert run.trigger_digest is None

    def test_workflow_run_lifecycle(self):
        """Test WorkflowRun lifecycle methods."""
        run = WorkflowRun(
            run_id="run_123",
            workflow_id="workflow_456",
            version="1.0",
            user_id="user_123",
            status=RunStatus.RUNNING,
            started_at=datetime.now()
        )
        
        # Test status updates
        assert run.status == RunStatus.RUNNING
        assert run.started_at is not None
        
        # Test completion
        run.status = RunStatus.SUCCESS
        run.finished_at = datetime.now()
        assert run.status == RunStatus.SUCCESS
        assert run.finished_at is not None

    def test_workflow_run_attributes(self):
        """Test WorkflowRun attributes."""
        run = WorkflowRun(
            run_id="run_123",
            workflow_id="workflow_456",
            version="1.0",
            user_id="user_123",
            status=RunStatus.RUNNING,
            started_at=datetime.now()
        )
        
        # Test that all required attributes are present
        assert hasattr(run, 'run_id')
        assert hasattr(run, 'workflow_id')
        assert hasattr(run, 'version')
        assert hasattr(run, 'user_id')
        assert hasattr(run, 'status')
        assert hasattr(run, 'started_at')
        assert hasattr(run, 'finished_at')
        assert hasattr(run, 'trigger_digest')


class TestWorkflowExecutor:
    """Test the WorkflowExecutor class."""
    
    def test_workflow_executor_initialization(self):
        """Test WorkflowExecutor initialization."""
        with patch('services.executor.executor.ComposioClient') as mock_composio, \
             patch('services.executor.executor.StateStore') as mock_state, \
             patch('services.executor.executor.IdempotencyCache') as mock_cache:
            
            executor = WorkflowExecutor(
                composio_client=mock_composio,
                state_store=mock_state,
                idempotency_cache=mock_cache
            )
            
            assert executor.composio_client == mock_composio
            assert executor.state_store == mock_state
            assert executor.idempotency_cache == mock_cache

    @pytest.mark.asyncio
    async def test_execute_workflow_async(self):
        """Test async workflow execution."""
        with patch('services.executor.executor.ComposioClient') as mock_composio, \
             patch('services.executor.executor.StateStore') as mock_state, \
             patch('services.executor.executor.IdempotencyCache') as mock_cache:
            
            executor = WorkflowExecutor(
                composio_client=mock_composio,
                state_store=mock_state,
                idempotency_cache=mock_cache
            )
            
            # Mock the execution method
            executor.execute_workflow = AsyncMock(return_value={"status": "completed"})
            
            result = await executor.execute_workflow_async("workflow_123", {"input": "data"})
            
            assert result == {"status": "completed"}
            executor.execute_workflow.assert_called_once_with("workflow_123", {"input": "data"})

    def test_execute_workflow_sync(self):
        """Test sync workflow execution."""
        with patch('services.executor.executor.ComposioClient') as mock_composio, \
             patch('services.executor.executor.StateStore') as mock_state, \
             patch('services.executor.executor.IdempotencyCache') as mock_cache:
            
            executor = WorkflowExecutor(
                composio_client=mock_composio,
                state_store=mock_state,
                idempotency_cache=mock_cache
            )
            
            # Mock the execution method
            executor.execute_workflow = Mock(return_value={"status": "completed"})
            
            result = executor.execute_workflow_sync("workflow_123", {"input": "data"})
            
            assert result == {"status": "completed"}
            executor.execute_workflow.assert_called_once_with("workflow_123", {"input": "data"})

    def test_validate_workflow_dsl(self):
        """Test workflow DSL validation."""
        with patch('services.executor.executor.ComposioClient') as mock_composio, \
             patch('services.executor.executor.StateStore') as mock_state, \
             patch('services.executor.executor.IdempotencyCache') as mock_cache:
            
            executor = WorkflowExecutor(
                composio_client=mock_composio,
                state_store=mock_state,
                idempotency_cache=mock_cache
            )
            
            # Valid DSL
            valid_dsl = {
                "nodes": [
                    {"id": "node1", "type": "trigger"},
                    {"id": "node2", "type": "action"}
                ],
                "edges": [{"from": "node1", "to": "node2"}]
            }
            
            # This would depend on your validation logic
            # For now, we'll just test that the method exists
            assert hasattr(executor, 'validate_workflow_dsl')

    def test_create_execution_plan(self):
        """Test execution plan creation."""
        with patch('services.executor.executor.ComposioClient') as mock_composio, \
             patch('services.executor.executor.StateStore') as mock_state, \
             patch('services.executor.executor.IdempotencyCache') as mock_cache:
            
            executor = WorkflowExecutor(
                composio_client=mock_composio,
                state_store=mock_state,
                idempotency_cache=mock_cache
            )
            
            dsl = {
                "nodes": [
                    {"id": "node1", "type": "trigger"},
                    {"id": "node2", "type": "action"}
                ],
                "edges": [{"from": "node1", "to": "node2"}]
            }
            
            # This would depend on your execution planning logic
            # For now, we'll just test that the method exists
            assert hasattr(executor, 'create_execution_plan')
