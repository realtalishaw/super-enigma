"""
Run monitoring routes.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timezone

from ...models import RunCreate, RunResponse

router = APIRouter(tags=["Runs"])

# Mock data storage (shared with execution.py in real implementation)
runs = {}


@router.get("")
async def list_runs(
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """List workflow runs with optional filtering"""
    filtered_runs = list(runs.values())
    
    if workflow_id:
        filtered_runs = [run for run in filtered_runs if run["workflow_id"] == workflow_id]
    
    if status:
        filtered_runs = [run for run in filtered_runs if run["status"] == status]
    
    # Apply pagination
    paginated_runs = filtered_runs[offset:offset + limit]
    
    return {
        "runs": paginated_runs,
        "total": len(filtered_runs),
        "limit": limit,
        "offset": offset
    }


@router.get("/{run_id}")
async def get_run(run_id: str):
    """Get a specific run by ID"""
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return RunResponse(**runs[run_id])


@router.get("/stream")
async def stream_runs():
    """Stream real-time run updates (mock implementation)"""
    # In a real implementation, this would use Server-Sent Events or WebSockets
    return {
        "message": "Streaming not implemented in mock version",
        "suggestion": "Use individual run endpoints for real-time updates"
    }
