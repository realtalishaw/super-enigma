"""
Workflow Execution Engine Package

A microservice for executing DAG workflows using Composio for tool execution.
Supports idempotency, retries, conditional logic, parallel execution, joins, and loops.

Main exports:
- WorkflowExecutor: Main execution engine class
- execute_workflow_async: Async function for executing workflows
- execute_workflow_sync: Sync function for executing workflows
- create_executor: Factory function for creating executor instances
- run_workflow: Convenience function for running workflows
"""

from .executor import (
    WorkflowExecutor,
    ComposioClient,
    StateStore,
    IdempotencyCache,
    ExecutionContext,
    NodeExecution,
    WorkflowRun,
    NodeType,
    NodeStatus,
    RunStatus,
    create_executor,
    execute_workflow_async,
    execute_workflow_sync
)

from .run_workflow import run_workflow, run_workflow_async

__all__ = [
    # Main classes
    "WorkflowExecutor",
    "ComposioClient", 
    "StateStore",
    "IdempotencyCache",
    "ExecutionContext",
    "NodeExecution",
    "WorkflowRun",
    
    # Enums
    "NodeType",
    "NodeStatus", 
    "RunStatus",
    
    # Factory functions
    "create_executor",
    
    # Execution functions
    "execute_workflow_async",
    "execute_workflow_sync",
    "run_workflow",
    "run_workflow_async"
]

__version__ = "1.0.0"
