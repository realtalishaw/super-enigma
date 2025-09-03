"""
Refactored main FastAPI application with separated route modules.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio

# Import route modules
from api.routes import (
    api_router,
    catalog_router,
    auth_router
)

# Import cache service
from api.cache_service import global_cache_service

# Import enhanced logging
from core.logging_config import get_logger
from api.middleware import add_logging_middleware

logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Workflow Orchestration API 2.0",
    description="Backend APIs for planning, creating, testing, activating, and observing AI-planned workflows that execute via Composio (MCP/SDK). Workflows are represented as DSL JSON.",
    version="1.0.0",
    openapi_tags=[
        {
            "name": "Auth",
            "description": "Authentication and session management endpoints"
        },

        {
            "name": "Integrations",
            "description": "Integration management endpoints"
        },
        {
            "name": "Suggestions",
            "description": "Workflow suggestion endpoints"
        },
        {
            "name": "Preferences",
            "description": "User preferences endpoints"
        },

        {
            "name": "Catalog",
            "description": "Integration catalog and tool management"
        }
    ]
)

@app.on_event("startup")
async def startup_event():
    """Initialize services when the server starts"""
    logger.info("🚀 Starting Weave API server...")
    
    # Initialize global cache service
    logger.info("📚 Initializing global cache service...")
    await global_cache_service.initialize()
    
    # Log cache status
    cache_status = global_cache_service.get_cache_status()
    health_status = global_cache_service.get_health_status()
    
    logger.info(f"📊 Cache Status: {cache_status['provider_count']} providers loaded")
    logger.info(f"🏥 Health Status: {'✅ Healthy' if health_status['healthy'] else '❌ Unhealthy'}")
    
    if not health_status['ready_for_requests']:
        logger.warning("⚠️  Cache service not ready for requests - some functionality may be limited")
    
    logger.info("🎉 Weave API server startup complete!")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services when the server shuts down"""
    logger.info("🛑 Shutting down Weave API server...")
    
    # Clear cache
    global_cache_service.clear_cache()
    logger.info("🗑️  Cache cleared")
    
    logger.info("👋 Weave API server shutdown complete!")

# Add logging middleware first (for request tracking)
add_logging_middleware(app)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=False,  # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all route modules
app.include_router(api_router)
app.include_router(catalog_router)
app.include_router(auth_router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Workflow Orchestration API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }
