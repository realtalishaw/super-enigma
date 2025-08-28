"""
Run execution routes.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timezone

from ...models import RunCreate, RunResponse

router = APIRouter(tags=["Runs"])

# Mock data storage
runs = {}


@router.post("")
async def create_run(request: RunCreate):
    """Create a new run"""
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    runs[run_id] = {
        "id": run_id,
        "workflow_id": request.workflow_id,
        "status": "running",
        "started_at": now,
        "completed_at": None,
        "result": None,
        "error": None,
        "execution_time_ms": None,
        "trigger_data": request.trigger_data
    }
    
    # Mock execution completion
    import asyncio
    await asyncio.sleep(0.1)  # Simulate execution time
    
    runs[run_id]["status"] = "completed"
    runs[run_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    runs[run_id]["result"] = {"output": "Mock execution completed successfully"}
    runs[run_id]["execution_time_ms"] = 100
    
    return RunResponse(**runs[run_id])
