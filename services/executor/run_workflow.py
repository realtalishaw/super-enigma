#!/usr/bin/env python3
"""
Simple script to run workflows programmatically

Usage:
    from services.executor.run_workflow import run_workflow
    
    # Run a workflow
    run_id = run_workflow(
        dag=workflow_dag,
        event_payload=event_data,
        user_id="user123",
        workflow_id="wf001"
    )
"""

import asyncio
import os
from typing import Dict, Any, Optional

from .executor import execute_workflow_async, execute_workflow_sync

def run_workflow(dag: Dict[str, Any], 
                 event_payload: Dict[str, Any],
                 user_id: str,
                 workflow_id: Optional[str] = None,
                 version: str = "1.0",
                 composio_base_url: Optional[str] = None,
                 composio_api_key: Optional[str] = None,
                 async_execution: bool = False) -> str:
    """
    Run a workflow synchronously or asynchronously
    
    Args:
        dag: DAG JSON conforming to schema
        event_payload: Event data from trigger
        user_id: User executing the workflow
        workflow_id: ID of the workflow (auto-generated if not provided)
        version: Version of the workflow
        composio_base_url: Composio API base URL
        composio_api_key: Composio API key
        async_execution: Whether to run asynchronously
        
    Returns:
        run_id: Unique identifier for this execution
        
    Raises:
        ValueError: If required parameters are missing
        Exception: If workflow execution fails
    """
    
    # Get Composio credentials from environment if not provided
    if not composio_base_url:
        composio_base_url = os.getenv("COMPOSIO_BASE_URL")
    if not composio_api_key:
        composio_api_key = os.getenv("COMPOSIO_API_KEY")
    
    if not composio_base_url or not composio_api_key:
        raise ValueError(
            "Composio base URL and API key are required. "
            "Set COMPOSIO_BASE_URL and COMPOSIO_API_KEY environment variables "
            "or provide them as parameters."
        )
    
    # Generate workflow ID if not provided
    if not workflow_id:
        import time
        workflow_id = f"wf_{int(time.time())}"
    
    if async_execution:
        # Return the coroutine for async execution
        return execute_workflow_async(
            dag=dag,
            event_payload=event_payload,
            user_id=user_id,
            workflow_id=workflow_id,
            version=version,
            composio_base_url=composio_base_url,
            composio_api_key=composio_api_key
        )
    else:
        # Run synchronously
        return execute_workflow_sync(
            dag=dag,
            event_payload=event_payload,
            user_id=user_id,
            workflow_id=workflow_id,
            version=version,
            composio_base_url=composio_base_url,
            composio_api_key=composio_api_key
        )

async def run_workflow_async(dag: Dict[str, Any],
                            event_payload: Dict[str, Any],
                            user_id: str,
                            workflow_id: Optional[str] = None,
                            version: str = "1.0",
                            composio_base_url: Optional[str] = None,
                            composio_api_key: Optional[str] = None) -> str:
    """
    Run a workflow asynchronously
    
    Args:
        dag: DAG JSON conforming to schema
        event_payload: Event data from trigger
        user_id: User executing the workflow
        workflow_id: ID of the workflow (auto-generated if not provided)
        version: Version of the workflow
        composio_base_url: Composio API base URL
        composio_api_key: Composio API key
        
    Returns:
        run_id: Unique identifier for this execution
    """
    
    # Get Composio credentials from environment if not provided
    if not composio_base_url:
        composio_base_url = os.getenv("COMPOSIO_BASE_URL")
    if not composio_api_key:
        composio_api_key = os.getenv("COMPOSIO_API_KEY")
    
    if not composio_base_url or not composio_api_key:
        raise ValueError(
            "Composio base URL and API key are required. "
            "Set COMPOSIO_BASE_URL and COMPOSIO_API_KEY environment variables "
            "or provide them as parameters."
        )
    
    # Generate workflow ID if not provided
    if not workflow_id:
        import time
        workflow_id = f"wf_{int(time.time())}"
    
    return await execute_workflow_async(
        dag=dag,
        event_payload=event_payload,
        user_id=user_id,
        workflow_id=workflow_id,
        version=version,
        composio_base_url=composio_base_url,
        composio_api_key=composio_api_key
    )

# Convenience function for running from command line
def main():
    """Simple command line interface for running workflows"""
    import json
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python run_workflow.py <dag_file> <event_file> <user_id> [workflow_id]")
        sys.exit(1)
    
    dag_file = sys.argv[1]
    event_file = sys.argv[2]
    user_id = sys.argv[3]
    workflow_id = sys.argv[4] if len(sys.argv) > 4 else None
    
    try:
        # Load DAG and event data
        with open(dag_file, 'r') as f:
            dag = json.load(f)
        
        with open(event_file, 'r') as f:
            event_payload = json.load(f)
        
        # Run workflow
        run_id = run_workflow(dag, event_payload, user_id, workflow_id)
        print(f"✅ Workflow executed successfully. Run ID: {run_id}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
