"""
FastAPI endpoints for the Cron Scheduler service.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from registrar import SchedulerRegistrar
from worker import SchedulerWorker
from database import SchedulerDatabase
from run_launcher import RunLauncher, WorkflowStore, ExecutorClient
from models import ScheduleInput, SchedulePreview
from core.logging_config import get_logger

logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Cron Scheduler Service",
    description="Service for managing cron-based workflow schedules",
    version="1.0.0"
)

# Global instances
db: Optional[SchedulerDatabase] = None
registrar: Optional[SchedulerRegistrar] = None
worker: Optional[SchedulerWorker] = None
run_launcher: Optional[RunLauncher] = None


def get_db() -> SchedulerDatabase:
    """Dependency to get database instance."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return db


def get_registrar() -> SchedulerRegistrar:
    """Dependency to get registrar instance."""
    if registrar is None:
        raise HTTPException(status_code=500, detail="Registrar not initialized")
    return registrar


def get_worker() -> SchedulerWorker:
    """Dependency to get worker instance."""
    if worker is None:
        raise HTTPException(status_code=500, detail="Worker not initialized")
    return worker


@app.on_event("startup")
async def startup_event():
    """Initialize service components on startup."""
    global db, registrar, worker, run_launcher
    
    try:
        # Initialize database
        db = SchedulerDatabase()
        
        # Initialize workflow store and executor client
        workflow_store = WorkflowStore()
        executor_client = ExecutorClient()
        
        # Initialize run launcher
        run_launcher = RunLauncher(workflow_store, executor_client)
        
        # Initialize registrar
        registrar = SchedulerRegistrar(db)
        
        # Initialize worker
        worker = SchedulerWorker(db, run_launcher)
        
        logger.info("Scheduler service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize scheduler service: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global worker
    
    if worker:
        worker.stop()
        logger.info("Scheduler worker stopped")


# API Models
class ScheduleResponse(BaseModel):
    schedule_id: str
    next_run_at: str


class PauseRequest(BaseModel):
    paused: bool = True


class StatusResponse(BaseModel):
    status: str
    worker_status: Dict[str, Any]


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "cron-scheduler"}


# Schedule management endpoints
@app.post("/schedules/upsert", response_model=ScheduleResponse)
async def upsert_schedule(
    input_data: ScheduleInput,
    registrar: SchedulerRegistrar = Depends(get_registrar)
):
    """Create or update a schedule."""
    try:
        result = registrar.upsert_schedule(input_data)
        return ScheduleResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to upsert schedule: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/schedules/{schedule_id}/pause")
async def pause_schedule(
    schedule_id: str,
    request: PauseRequest,
    registrar: SchedulerRegistrar = Depends(get_registrar)
):
    """Pause or unpause a schedule."""
    try:
        registrar.pause_schedule(schedule_id, request.paused)
        return {"message": f"Schedule {schedule_id} {'paused' if request.paused else 'unpaused'}"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to pause/unpause schedule: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    registrar: SchedulerRegistrar = Depends(get_registrar)
):
    """Delete a schedule."""
    try:
        registrar.delete_schedule(schedule_id)
        return {"message": f"Schedule {schedule_id} deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete schedule: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/schedules/{schedule_id}", response_model=SchedulePreview)
async def get_schedule(
    schedule_id: str,
    registrar: SchedulerRegistrar = Depends(get_registrar)
):
    """Get a schedule with preview of next fire times."""
    try:
        schedule_preview = registrar.get_schedule(schedule_id)
        if not schedule_preview:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return schedule_preview
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get schedule: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/schedules")
async def list_schedules(
    user_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    limit: int = 100,
    registrar: SchedulerRegistrar = Depends(get_registrar)
):
    """List schedules with optional filtering."""
    try:
        schedules = registrar.list_schedules(user_id, workflow_id, limit)
        return {"schedules": [schedule.dict() for schedule in schedules]}
    except Exception as e:
        logger.error(f"Failed to list schedules: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Worker management endpoints
@app.post("/worker/start")
async def start_worker(worker: SchedulerWorker = Depends(get_worker)):
    """Start the scheduler worker."""
    try:
        worker.start()
        return {"message": "Worker started successfully"}
    except Exception as e:
        logger.error(f"Failed to start worker: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/worker/stop")
async def stop_worker(worker: SchedulerWorker = Depends(get_worker)):
    """Stop the scheduler worker."""
    try:
        worker.stop()
        return {"message": "Worker stopped successfully"}
    except Exception as e:
        logger.error(f"Failed to stop worker: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/worker/status", response_model=StatusResponse)
async def get_worker_status(worker: SchedulerWorker = Depends(get_worker)):
    """Get the current status of the worker."""
    try:
        worker_status = worker.get_status()
        status = "running" if worker_status["running"] else "stopped"
        
        return StatusResponse(
            status=status,
            worker_status=worker_status
        )
    except Exception as e:
        logger.error(f"Failed to get worker status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Run launcher endpoint
@app.post("/run-launcher/start")
async def start_workflow(
    workflow_id: str,
    version: int,
    user_id: str,
    scheduled_for: str,
    idempotency_key: str,
    run_launcher: RunLauncher = Depends(lambda: run_launcher)
):
    """Start a workflow execution."""
    try:
        from datetime import datetime
        
        # Parse scheduled_for timestamp
        scheduled_for_dt = datetime.fromisoformat(scheduled_for.replace('Z', '+00:00'))
        
        success = run_launcher.start(
            workflow_id,
            version,
            user_id,
            scheduled_for_dt,
            idempotency_key
        )
        
        if success:
            return {"message": "Workflow started successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to start workflow")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp: {e}")
    except Exception as e:
        logger.error(f"Failed to start workflow: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Metrics and observability endpoints
@app.get("/metrics")
async def get_metrics(db: SchedulerDatabase = Depends(get_db)):
    """Get basic metrics about the scheduler."""
    try:
        # This is a simplified implementation
        # In production, you'd want more sophisticated metrics
        return {
            "total_schedules": 0,  # TODO: implement
            "active_schedules": 0,  # TODO: implement
            "paused_schedules": 0,  # TODO: implement
            "total_runs": 0,  # TODO: implement
            "successful_runs": 0,  # TODO: implement
            "failed_runs": 0  # TODO: implement
        }
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/schedules/{schedule_id}/runs")
async def get_schedule_runs(
    schedule_id: str,
    limit: int = 10,
    db: SchedulerDatabase = Depends(get_db)
):
    """Get recent runs for a schedule."""
    try:
        runs = db.get_recent_runs(schedule_id, limit)
        return {"runs": [run.dict() for run in runs]}
    except Exception as e:
        logger.error(f"Failed to get schedule runs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
