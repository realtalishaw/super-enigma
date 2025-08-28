"""
RunLauncher for starting workflow executions from scheduled triggers.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)


class RunLauncher:
    """Launches workflow runs from scheduled triggers."""
    
    def __init__(self, workflow_store=None, executor_client=None):
        """
        Initialize the RunLauncher.
        
        Args:
            workflow_store: Interface to load workflow DAGs
            executor_client: Interface to the workflow executor
        """
        self.workflow_store = workflow_store
        self.executor_client = executor_client
    
    def start(
        self, 
        workflow_id: str, 
        version: int, 
        user_id: str, 
        scheduled_for: datetime, 
        idempotency_key: str
    ) -> bool:
        """
        Start a workflow execution.
        
        Args:
            workflow_id: ID of the workflow to execute
            version: Version of the workflow
            user_id: ID of the user who owns the workflow
            scheduled_for: When the workflow was scheduled to run
            idempotency_key: Unique key to prevent duplicate runs
            
        Returns:
            True if the workflow was started successfully, False otherwise
        """
        try:
            logger.info(f"Starting workflow {workflow_id} v{version} for user {user_id}")
            
            # Load the workflow DAG
            dag = self._load_workflow_dag(workflow_id, version)
            if not dag:
                logger.error(f"Failed to load workflow {workflow_id} v{version}")
                return False
            
            # Prepare execution metadata
            meta = {
                "source": "schedule",
                "user_id": user_id,
                "scheduled_for": scheduled_for.isoformat(),
                "idempotency_key": idempotency_key,
                "triggered_at": datetime.utcnow().isoformat()
            }
            
            # Start the workflow execution
            success = self._execute_workflow(dag, meta)
            
            if success:
                logger.info(f"Workflow {workflow_id} v{version} started successfully")
            else:
                logger.error(f"Failed to start workflow {workflow_id} v{version}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error starting workflow {workflow_id}: {e}")
            return False
    
    def _load_workflow_dag(self, workflow_id: str, version: int) -> Optional[Dict[str, Any]]:
        """
        Load workflow DAG from the workflow store.
        
        Args:
            workflow_id: ID of the workflow
            version: Version of the workflow
            
        Returns:
            Workflow DAG as a dictionary, or None if loading failed
        """
        try:
            if self.workflow_store:
                # Use the provided workflow store
                return self.workflow_store.load_dag(workflow_id, version)
            else:
                # Fallback to a mock implementation for testing
                logger.warning("No workflow store provided, using mock DAG")
                return self._create_mock_dag(workflow_id, version)
                
        except Exception as e:
            logger.error(f"Failed to load workflow DAG: {e}")
            return None
    
    def _execute_workflow(self, dag: Dict[str, Any], meta: Dict[str, Any]) -> bool:
        """
        Execute the workflow using the executor.
        
        Args:
            dag: Workflow DAG
            meta: Execution metadata
            
        Returns:
            True if execution was started successfully
        """
        try:
            if self.executor_client:
                # Use the provided executor client
                return self.executor_client.run(dag, meta)
            else:
                # Fallback to a mock implementation for testing
                logger.warning("No executor client provided, using mock execution")
                return self._mock_execute_workflow(dag, meta)
                
        except Exception as e:
            logger.error(f"Failed to execute workflow: {e}")
            return False
    
    def _create_mock_dag(self, workflow_id: str, version: int) -> Dict[str, Any]:
        """Create a mock workflow DAG for testing purposes."""
        return {
            "workflow_id": workflow_id,
            "version": version,
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "next": "action1"
                },
                {
                    "id": "action1",
                    "type": "action",
                    "action": "mock_action",
                    "next": "end"
                },
                {
                    "id": "end",
                    "type": "end"
                }
            ],
            "metadata": {
                "name": f"Mock Workflow {workflow_id}",
                "description": "Mock workflow for testing"
            }
        }
    
    def _mock_execute_workflow(self, dag: Dict[str, Any], meta: Dict[str, Any]) -> bool:
        """Mock workflow execution for testing purposes."""
        logger.info(f"Mock executing workflow {dag.get('workflow_id')} with meta: {meta}")
        # Simulate successful execution
        return True


class WorkflowStore:
    """Interface for loading workflow DAGs."""
    
    def __init__(self, storage_path: str = "workflows"):
        """
        Initialize the workflow store.
        
        Args:
            storage_path: Path to workflow storage
        """
        self.storage_path = storage_path
    
    def load_dag(self, workflow_id: str, version: int) -> Optional[Dict[str, Any]]:
        """
        Load a workflow DAG.
        
        Args:
            workflow_id: ID of the workflow
            version: Version of the workflow
            
        Returns:
            Workflow DAG as a dictionary, or None if not found
        """
        try:
            # This is a simplified implementation
            # In production, you'd load from a database or file system
            import os
            import json
            
            filename = f"{workflow_id}_v{version}.json"
            filepath = os.path.join(self.storage_path, filename)
            
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    return json.load(f)
            else:
                logger.warning(f"Workflow file not found: {filepath}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to load workflow DAG: {e}")
            return None


class ExecutorClient:
    """Interface for communicating with the workflow executor."""
    
    def __init__(self, executor_url: str = None):
        """
        Initialize the executor client.
        
        Args:
            executor_url: URL of the executor service
        """
        self.executor_url = executor_url
    
    def run(self, dag: Dict[str, Any], meta: Dict[str, Any]) -> bool:
        """
        Start a workflow execution.
        
        Args:
            dag: Workflow DAG
            meta: Execution metadata
            
        Returns:
            True if execution was started successfully
        """
        try:
            if self.executor_url:
                # Make HTTP call to executor service
                return self._http_execute(dag, meta)
            else:
                # Direct function call to executor
                return self._direct_execute(dag, meta)
                
        except Exception as e:
            logger.error(f"Failed to execute workflow: {e}")
            return False
    
    def _http_execute(self, dag: Dict[str, Any], meta: Dict[str, Any]) -> bool:
        """Execute workflow via HTTP call."""
        try:
            import httpx
            
            response = httpx.post(
                f"{self.executor_url}/execute",
                json={
                    "dag": dag,
                    "meta": meta
                },
                timeout=30.0
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"HTTP execution failed: {e}")
            return False
    
    def _direct_execute(self, dag: Dict[str, Any], meta: Dict[str, Any]) -> bool:
        """Execute workflow via direct function call."""
        try:
            # Import and call the executor directly
            # This assumes the executor is available in the same process
            from ..executor.executor import Executor
            
            executor = Executor()
            executor.run(dag, meta)
            return True
            
        except ImportError:
            logger.warning("Executor not available for direct execution")
            return False
        except Exception as e:
            logger.error(f"Direct execution failed: {e}")
            return False
