"""
Runs routes package.
"""

from api.routes.runs.execution import router as execution_router
from api.routes.runs.monitoring import router as monitoring_router

# Create a combined runs router
from fastapi import APIRouter

runs_router = APIRouter(tags=["Runs"])

# Include all run sub-routers with their own prefixes
runs_router.include_router(execution_router, prefix="/runs")
runs_router.include_router(monitoring_router, prefix="/runs")

__all__ = [
    "runs_router",
    "execution_router",
    "monitoring_router"
]
