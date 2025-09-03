"""
API integrations routes.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bson import ObjectId

from core.config import settings
from database.config import get_database_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["Integrations"])

# System endpoints
@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2025-01-28T00:00:00Z",
        "version": "1.0.0"
    }

@router.get("/rate-limiting/status")
async def get_rate_limiting_status() -> Dict[str, Any]:
    """Get current rate limiting status for Claude API calls"""
    try:
        # Import here to avoid circular imports
        from services.dsl_generator.rate_limiter import get_global_rate_limiter
        
        rate_limiter = get_global_rate_limiter()
        stats = rate_limiter.get_stats()
        
        return {
            "status": "success",
            "rate_limiting": stats,
            "timestamp": "2025-01-28T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Failed to get rate limiting status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get rate limiting status: {str(e)}")

@router.post("/rate-limiting/configure")
async def configure_rate_limiting(config: Dict[str, Any]) -> Dict[str, Any]:
    """Configure rate limiting parameters"""
    try:
        from services.dsl_generator.rate_limiter import set_global_rate_limiter_config, RateLimitConfig
        
        # Extract configuration parameters
        rate_limit_config = RateLimitConfig(
            requests_per_minute=config.get("requests_per_minute", 20),
            burst_limit=config.get("burst_limit", 5),
            base_delay=config.get("base_delay", 2.0),
            max_delay=config.get("max_delay", 30.0),
            jitter_factor=config.get("jitter_factor", 0.25)
        )
        
        set_global_rate_limiter_config(rate_limit_config)
        
        return {
            "status": "success",
            "message": "Rate limiting configuration updated",
            "config": {
                "requests_per_minute": rate_limit_config.requests_per_minute,
                "burst_limit": rate_limit_config.burst_limit,
                "base_delay": rate_limit_config.base_delay,
                "max_delay": rate_limit_config.max_delay,
                "jitter_factor": rate_limit_config.jitter_factor
            },
            "timestamp": "2025-01-28T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Failed to configure rate limiting: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to configure rate limiting: {str(e)}")

@router.get("/ai-client/status")
async def get_ai_client_status() -> Dict[str, Any]:
    """Get AI client status and configuration"""
    try:
        from services.dsl_generator.ai_client import AIClient
        
        # Create a temporary client to get status
        client = AIClient()
        model_info = client.get_model_info()
        rate_stats = client.get_rate_limiting_stats()
        
        return {
            "status": "success",
            "ai_client": {
                "model_info": model_info,
                "rate_limiting_stats": rate_stats
            },
            "timestamp": "2025-01-28T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Failed to get AI client status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get AI client status: {str(e)}")

# Global MongoDB client
_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None

async def get_database_client() -> AsyncIOMotorDatabase:
    """Get MongoDB database client"""
    global _client, _database
    
    if _client is None:
        database_url = get_database_url()
        _client = AsyncIOMotorClient(database_url)
        _database = _client.get_database()
    
    return _database

@router.get("")
async def get_integrations(
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = 0
):
    """Get available integrations (toolkits) from the database with pagination support"""
    try:
        database = await get_database_client()
        
        # Build base filter
        base_filter = {"is_deprecated": False}
        
        # Add search filter
        if search:
            base_filter["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        
        # Get total count
        total_count = await database.toolkits.count_documents(base_filter)
        
        # Execute query with pagination
        cursor = database.toolkits.find(base_filter).sort("name", 1)
        
        if offset:
            cursor = cursor.skip(offset)
        if limit:
            cursor = cursor.limit(limit)
        
        integrations = []
        async for row in cursor:
            integration = {
                "id": str(row["_id"]),
                "slug": row["slug"],
                "name": row["name"],
                "description": row.get("description", ""),
                "logo": row.get("logo_url") or f"/static/icons/{row['slug'].lower()}.svg",  # Fallback to static icon
                "category": row.get("category", "other")  # Default to "other" if no category
            }
            integrations.append(integration)
        
        return {
            "items": integrations,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "hasMore": limit and (offset + limit) < total_count
        }
        
    except ConnectionError as e:
        logger.error(f"Database connection failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Database service unavailable: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error fetching integrations from database: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch integrations from database: {str(e)}"
        )

@router.get("/search")
async def search_integrations(
    q: str,
    limit: Optional[int] = 20,
    offset: Optional[int] = 0
):
    """Search integrations by query string with pagination"""
    try:
        database = await get_database_client()
        
        # Build search query
        search_query = {
            "$or": [
                {"name": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}},
                {"slug": {"$regex": q, "$options": "i"}}
            ],
            "is_deprecated": False
        }
        
        # Get total count
        total_count = await database.toolkits.count_documents(search_query)
        
        # Execute query with pagination
        cursor = database.toolkits.find(search_query).sort("name", 1)
        
        if offset:
            cursor = cursor.skip(offset)
        if limit:
            cursor = cursor.limit(limit)
        
        integrations = []
        async for row in cursor:
            integration = {
                "id": str(row["_id"]),
                "slug": row["slug"],
                "name": row["name"],
                "description": row.get("description", ""),
                "logo": row.get("logo_url") or f"/static/icons/{row['slug'].lower()}.svg",
                "category": row.get("category", "other")
            }
            integrations.append(integration)
        
        return {
            "items": integrations,
            "query": q,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error searching integrations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search integrations: {str(e)}"
        )

@router.get("/{slug}")
async def get_integration_by_slug(slug: str):
    """Get a specific integration by its slug"""
    try:
        database = await get_database_client()
        
        integration = await database.toolkits.find_one({
            "slug": slug,
            "is_deprecated": False
        })
        
        if not integration:
            raise HTTPException(
                status_code=404,
                detail=f"Integration with slug '{slug}' not found"
            )
        
        return {
            "id": str(integration["_id"]),
            "slug": integration["slug"],
            "name": integration["name"],
            "description": integration.get("description", ""),
            "logo": integration.get("logo_url") or f"/static/icons/{integration['slug'].lower()}.svg",
            "category": integration.get("category", "other"),
            "created_at": integration.get("created_at").isoformat() if integration.get("created_at") else None,
            "updated_at": integration.get("updated_at").isoformat() if integration.get("updated_at") else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching integration by slug '{slug}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch integration: {str(e)}"
        )
