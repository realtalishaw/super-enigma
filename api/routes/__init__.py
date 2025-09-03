"""
API Routes Package

This package contains all the route modules organized by functionality.
"""

from api.routes.api import api_router
from api.routes.catalog import catalog_router
from api.routes.auth import auth_router

__all__ = [
    "api_router", 
    "catalog_router",
    "auth_router"
]
