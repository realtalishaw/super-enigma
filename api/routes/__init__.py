"""
API Routes Package

This package contains all the route modules organized by functionality.
"""

from api.routes.system import router as system_router
from api.routes.frontend import frontend_router
from api.routes.runs import runs_router
from api.routes.catalog import catalog_router

from api.routes.auth import auth_router

__all__ = [
    "system_router",
    "frontend_router", 
    "runs_router",
    "catalog_router",

    "auth_router"
]
