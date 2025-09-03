"""
API routes package.
"""

from api.routes.api.integrations import router as integrations_router
from api.routes.api.suggestions import router as suggestions_router
from api.routes.api.preferences import router as preferences_router

# Create a combined API router
from fastapi import APIRouter

api_router = APIRouter(prefix="/api")

# Include all API sub-routers
api_router.include_router(integrations_router)
api_router.include_router(suggestions_router)
api_router.include_router(preferences_router)

__all__ = [
    "api_router",
    "integrations_router",
    "suggestions_router", 
    "preferences_router"
]
