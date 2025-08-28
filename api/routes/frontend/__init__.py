"""
Frontend routes package.
"""

from api.routes.frontend.integrations import router as integrations_router
from api.routes.frontend.suggestions import router as suggestions_router
from api.routes.frontend.preferences import router as preferences_router

# Create a combined frontend router
from fastapi import APIRouter

frontend_router = APIRouter(prefix="/api")

# Include all frontend sub-routers
frontend_router.include_router(integrations_router)
frontend_router.include_router(suggestions_router)
frontend_router.include_router(preferences_router)

__all__ = [
    "frontend_router",
    "integrations_router",
    "suggestions_router", 
    "preferences_router"
]
