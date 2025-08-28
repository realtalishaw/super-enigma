"""
Tests for the scheduler service.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio
from datetime import datetime, timedelta
from services.scheduler.models import Schedule, ScheduleRun
from services.scheduler.registrar import SchedulerRegistrar
from services.scheduler.worker import SchedulerWorker
from services.scheduler.run_launcher import RunLauncher


class TestSchedule:
    """Test the Schedule model."""
    
    def test_schedule_initialization(self):
        """Test Schedule initialization."""
        schedule = Schedule(
            id="schedule_123",
            workflow_id="workflow_456",
            cron_expression="0 0 * * *",
            timezone="UTC",
            is_active=True,
            metadata={"description": "Daily workflow"}
        )
        
        assert schedule.id == "schedule_123"
        assert schedule.workflow_id == "workflow_456"
        assert schedule.cron_expression == "0 0 * * *"
        assert schedule.timezone == "UTC"
        assert schedule.is_active is True
        assert schedule.metadata == {"description": "Daily workflow"}

    def test_schedule_validation(self):
        """Test Schedule validation."""
        # Valid cron expression
        valid_schedule = Schedule(
            id="schedule_123",
            workflow_id="workflow_456",
            cron_expression="0 0 * * *"
        )
        assert valid_schedule.cron_expression == "0 0 * * *"
        
        # Invalid cron expression should raise validation error
        with pytest.raises(Exception):
            Schedule(
                id="schedule_123",
                workflow_id="workflow_456",
                cron_expression="invalid_cron"
            )

    def test_schedule_activation(self):
        """Test Schedule activation/deactivation."""
        schedule = Schedule(
            id="schedule_123",
            workflow_id="workflow_456",
            cron_expression="0 0 * * *"
        )
        
        # Test activation
        schedule.activate()
        assert schedule.is_active is True
        
        # Test deactivation
        schedule.deactivate()
        assert schedule.is_active is False

    def test_schedule_next_run_calculation(self):
        """Test next run time calculation."""
        schedule = Schedule(
            id="schedule_123",
            workflow_id="workflow_456",
            cron_expression="0 0 * * *"  # Daily at midnight
        )
        
        # This would depend on your cron parsing logic
        # For now, we'll just test that the method exists
        assert hasattr(schedule, 'get_next_run_time')


class TestScheduleRun:
    """Test the ScheduleRun model."""
    
    def test_schedule_run_initialization(self):
        """Test ScheduleRun initialization."""
        run = ScheduleRun(
            id="run_123",
            schedule_id="schedule_456",
            workflow_id="workflow_789",
            status="pending",
            scheduled_time=datetime.now(),
            metadata={"trigger": "cron"}
        )
        
        assert run.id == "run_123"
        assert run.schedule_id == "schedule_456"
        assert run.workflow_id == "workflow_789"
        assert run.status == "pending"
        assert run.scheduled_time is not None
        assert run.metadata == {"trigger": "cron"}

    def test_schedule_run_status_transitions(self):
        """Test ScheduleRun status transitions."""
        run = ScheduleRun(
            id="run_123",
            schedule_id="schedule_456",
            workflow_id="workflow_789"
        )
        
        # Test status transitions
        run.start()
        assert run.status == "running"
        assert run.started_time is not None
        
        run.complete()
        assert run.status == "completed"
        assert run.completed_time is not None
        
        # Test failure
        run.fail("Test error")
        assert run.status == "failed"
        assert run.error == "Test error"

    def test_schedule_run_timing(self):
        """Test ScheduleRun timing functionality."""
        run = ScheduleRun(
            id="run_123",
            schedule_id="schedule_456",
            workflow_id="workflow_789"
        )
        
        # Test duration calculation
        run.start()
        import time
        time.sleep(0.1)  # Small delay
        
        duration = run.get_duration()
        assert duration > 0


class TestSchedulerRegistrar:
    """Test the SchedulerRegistrar class."""
    
    def test_scheduler_registrar_initialization(self):
        """Test SchedulerRegistrar initialization."""
        with patch('services.scheduler.registrar.redis.Redis') as mock_redis:
            registrar = SchedulerRegistrar(redis_url="redis://localhost:6379")
            
            assert registrar.redis_url == "redis://localhost:6379"
            mock_redis.assert_called_once()

    @patch('services.scheduler.registrar.redis.Redis')
    def test_register_schedule(self, mock_redis):
        """Test schedule registration."""
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        
        registrar = SchedulerRegistrar(redis_url="redis://localhost:6379")
        
        schedule = Schedule(
            id="schedule_123",
            workflow_id="workflow_456",
            cron_expression="0 0 * * *"
        )
        
        result = registrar.register_schedule(schedule)
        
        assert result is True
        mock_redis_instance.set.assert_called_once()

    @patch('services.scheduler.registrar.redis.Redis')
    def test_unregister_schedule(self, mock_redis):
        """Test schedule unregistration."""
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        
        registrar = SchedulerRegistrar(redis_url="redis://localhost:6379")
        
        result = registrar.unregister_schedule("schedule_123")
        
        assert result is True
        mock_redis_instance.delete.assert_called_once_with("schedule_123")

    @patch('services.scheduler.registrar.redis.Redis')
    def test_get_schedule(self, mock_redis):
        """Test getting a schedule."""
        mock_redis_instance = Mock()
        mock_redis_instance.get.return_value = '{"id": "schedule_123"}'
        mock_redis.return_value = mock_redis_instance
        
        registrar = SchedulerRegistrar(redis_url="redis://localhost:6379")
        
        result = registrar.get_schedule("schedule_123")
        
        assert result["id"] == "schedule_123"
        mock_redis_instance.get.assert_called_once_with("schedule_123")

    @patch('services.scheduler.registrar.redis.Redis')
    def test_list_schedules(self, mock_redis):
        """Test listing all schedules."""
        mock_redis_instance = Mock()
        mock_redis_instance.keys.return_value = ["schedule_1", "schedule_2"]
        mock_redis_instance.mget.return_value = ['{"id": "schedule_1"}', '{"id": "schedule_2"}']
        mock_redis.return_value = mock_redis_instance
        
        registrar = SchedulerRegistrar(redis_url="redis://localhost:6379")
        
        result = registrar.list_schedules()
        
        assert len(result) == 2
        assert result[0]["id"] == "schedule_1"
        assert result[1]["id"] == "schedule_2"


class TestSchedulerWorker:
    """Test the SchedulerWorker class."""
    
    def test_scheduler_worker_initialization(self):
        """Test SchedulerWorker initialization."""
        with patch('services.scheduler.worker.SchedulerRegistrar') as mock_registrar, \
             patch('services.scheduler.worker.RunLauncher') as mock_launcher:
            
            worker = SchedulerWorker(
                registrar=mock_registrar,
                run_launcher=mock_launcher,
                check_interval=60
            )
            
            assert worker.registrar == mock_registrar
            assert worker.run_launcher == mock_launcher
            assert worker.check_interval == 60
            assert worker.is_running is False

    @patch('services.scheduler.worker.asyncio.sleep')
    @patch('services.scheduler.worker.SchedulerWorker._check_schedules')
    async def test_worker_run_loop(self, mock_check_schedules, mock_sleep):
        """Test worker run loop."""
        with patch('services.scheduler.worker.SchedulerRegistrar') as mock_registrar, \
             patch('services.scheduler.worker.RunLauncher') as mock_launcher:
            
            worker = SchedulerWorker(
                registrar=mock_registrar,
                run_launcher=mock_launcher
            )
            
            # Mock the check method
            mock_check_schedules.return_value = None
            
            # Start the worker
            worker.start()
            assert worker.is_running is True
            
            # Stop the worker
            worker.stop()
            assert worker.is_running is False

    @patch('services.scheduler.worker.SchedulerWorker._check_schedules')
    def test_worker_start_stop(self, mock_check_schedules):
        """Test worker start and stop methods."""
        with patch('services.scheduler.worker.SchedulerRegistrar') as mock_registrar, \
             patch('services.scheduler.worker.RunLauncher') as mock_launcher:
            
            worker = SchedulerWorker(
                registrar=mock_registrar,
                run_launcher=mock_launcher
            )
            
            # Test start
            worker.start()
            assert worker.is_running is True
            
            # Test stop
            worker.stop()
            assert worker.is_running is False

    def test_worker_schedule_checking(self):
        """Test worker schedule checking logic."""
        with patch('services.scheduler.worker.SchedulerRegistrar') as mock_registrar, \
             patch('services.scheduler.worker.RunLauncher') as mock_launcher:
            
            worker = SchedulerWorker(
                registrar=mock_registrar,
                run_launcher=mock_launcher
            )
            
            # Mock schedules
            mock_schedules = [
                Schedule(
                    id="schedule_1",
                    workflow_id="workflow_1",
                    cron_expression="0 0 * * *"
                ),
                Schedule(
                    id="schedule_2",
                    workflow_id="workflow_2",
                    cron_expression="0 12 * * *"
                )
            ]
            
            mock_registrar.list_schedules.return_value = mock_schedules
            
            # This would depend on your schedule checking logic
            # For now, we'll just test that the method exists
            assert hasattr(worker, '_check_schedules')


class TestRunLauncher:
    """Test the RunLauncher class."""
    
    def test_run_launcher_initialization(self):
        """Test RunLauncher initialization."""
        with patch('services.scheduler.run_launcher.httpx.AsyncClient') as mock_client:
            launcher = RunLauncher(api_url="http://localhost:8000")
            
            assert launcher.api_url == "http://localhost:8000"
            mock_client.assert_called_once()

    @patch('services.scheduler.run_launcher.httpx.AsyncClient')
    async def test_launch_workflow_run(self, mock_client):
        """Test launching a workflow run."""
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"execution_id": "exec_123"}
        mock_client_instance.post.return_value = mock_response
        
        launcher = RunLauncher(api_url="http://localhost:8000")
        
        result = await launcher.launch_workflow_run(
            workflow_id="workflow_123",
            input_data={"test": "data"}
        )
        
        assert result["execution_id"] == "exec_123"
        mock_client_instance.post.assert_called_once()

    @patch('services.scheduler.run_launcher.httpx.AsyncClient')
    async def test_launch_workflow_run_error(self, mock_client):
        """Test error handling when launching a workflow run."""
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client_instance.post.return_value = mock_response
        
        launcher = RunLauncher(api_url="http://localhost:8000")
        
        with pytest.raises(Exception):
            await launcher.launch_workflow_run(
                workflow_id="workflow_123",
                input_data={"test": "data"}
            )

    @patch('services.scheduler.run_launcher.httpx.AsyncClient')
    async def test_launch_workflow_run_timeout(self, mock_client):
        """Test timeout handling when launching a workflow run."""
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock timeout
        mock_client_instance.post.side_effect = asyncio.TimeoutError()
        
        launcher = RunLauncher(api_url="http://localhost:8000")
        
        with pytest.raises(asyncio.TimeoutError):
            await launcher.launch_workflow_run(
                workflow_id="workflow_123",
                input_data={"test": "data"}
            )

    def test_run_launcher_url_building(self):
        """Test URL building for different endpoints."""
        launcher = RunLauncher(api_url="http://localhost:8000")
        
        # Test workflow execution endpoint
        execution_url = launcher._build_execution_url("workflow_123")
        expected_url = "http://localhost:8000/workflows/workflow_123/execute"
        assert execution_url == expected_url

    def test_run_launcher_headers(self):
        """Test that appropriate headers are set."""
        launcher = RunLauncher(api_url="http://localhost:8000")
        
        # Test default headers
        headers = launcher._get_headers()
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"

    @patch('services.scheduler.run_launcher.httpx.AsyncClient')
    async def test_launch_workflow_run_with_metadata(self, mock_client):
        """Test launching a workflow run with metadata."""
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"execution_id": "exec_123"}
        mock_client_instance.post.return_value = mock_response
        
        launcher = RunLauncher(api_url="http://localhost:8000")
        
        result = await launcher.launch_workflow_run(
            workflow_id="workflow_123",
            input_data={"test": "data"},
            metadata={"source": "scheduler", "schedule_id": "schedule_456"}
        )
        
        assert result["execution_id"] == "exec_123"
        
        # Verify the request was made with metadata
        call_args = mock_client_instance.post.call_args
        request_data = call_args[1]["json"]
        assert "metadata" in request_data
        assert request_data["metadata"]["source"] == "scheduler"
