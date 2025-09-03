"""
Catalog providers routes.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers", tags=["Catalog"])

async def get_global_cache_service():
    """Get the global cache service instance"""
    from api.cache_service import get_global_cache_service
    return await get_global_cache_service()

@router.get("/{provider_slug}")
async def get_provider(provider_slug: str):
    """Get toolkit information by slug with all associated tools using cached data"""
    try:
        # Get the global cache service
        cache_service = await get_global_cache_service()
        
        if not cache_service.is_initialized():
            logger.warning("Cache service not initialized, attempting to initialize")
            await cache_service.initialize()
        
        # Get cached catalog data
        catalog_cache = cache_service.get_catalog_cache()
        
        if not catalog_cache:
            logger.warning("No catalog cache available, falling back to direct database query")
            return await _fallback_get_provider_database(provider_slug)
        
        # Look for provider in cached data
        if provider_slug not in catalog_cache:
            raise HTTPException(
                status_code=404,
                detail=f"Provider '{provider_slug}' not found"
            )
        
        provider_data = catalog_cache[provider_slug]
        
        # Get actions and triggers
        actions = provider_data.get('actions', [])
        triggers = provider_data.get('triggers', [])
        
        # Build provider response
        provider = {
            "id": provider_data.get('id'),
            "slug": provider_slug,
            "name": provider_data.get('name', provider_slug),
            "description": provider_data.get('description'),
            "logo_url": provider_data.get('logo_url'),
            "website_url": provider_data.get('website_url'),
            "category": provider_data.get('category'),
            "version": provider_data.get('version'),
            "created_at": provider_data.get('created_at'),
            "updated_at": provider_data.get('updated_at'),
            "last_synced_at": provider_data.get('last_synced_at'),
            "stats": {
                "total_tools": len(actions) + len(triggers),
                "actions": len(actions),
                "triggers": len(triggers)
            },
            "tools": {
                "actions": actions,
                "triggers": triggers
            },
            "source": "cache"
        }
        
        return provider
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching provider '{provider_slug}' from cache: {e}")
        # Fallback to database query
        return await _fallback_get_provider_database(provider_slug)

async def _fallback_get_provider_database(provider_slug: str):
    """Fallback to direct database query for provider"""
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from database.config import get_database_url
        
        # Create database connection
        database_url = get_database_url()
        client = AsyncIOMotorClient(database_url)
        database = client.get_database()
        
        # Get toolkit information
        toolkit = await database.toolkits.find_one({
            "slug": provider_slug,
            "is_deprecated": False
        })
        
        if not toolkit:
            client.close()
            raise HTTPException(
                status_code=404,
                detail=f"Provider '{provider_slug}' not found"
            )
        
        # Get tools for this toolkit
        tools_cursor = database.tools.find({
            "toolkit_id": str(toolkit["_id"]),
            "is_deprecated": False
        }).sort([("tool_type", 1), ("name", 1)])
        
        tools_data = await tools_cursor.to_list(length=None)
        
        # Close database connection
        client.close()
        
        # Organize tools by type
        actions = []
        triggers = []
        
        for tool in tools_data:
            tool_info = {
                "id": str(tool["_id"]),
                "slug": tool.get("slug"),
                "name": tool["name"],
                "display_name": tool.get("display_name"),
                "description": tool["description"],
                "type": tool["tool_type"],
                "version": tool.get("version"),
                "input_schema": tool.get("input_schema"),
                "output_schema": tool.get("output_schema"),
                "tags": tool.get("tags", [])
            }
            
            if tool["tool_type"] == 'action':
                actions.append(tool_info)
            elif tool["tool_type"] == 'trigger':
                triggers.append(tool_info)
        
        # Build provider response
        provider = {
            "id": str(toolkit["_id"]),
            "slug": toolkit["slug"],
            "name": toolkit["name"],
            "description": toolkit["description"],
            "logo_url": toolkit.get("logo_url"),
            "website_url": toolkit.get("website_url"),
            "category": toolkit.get("category"),
            "version": toolkit.get("version"),
            "created_at": toolkit.get("created_at").isoformat() if toolkit.get("created_at") else None,
            "updated_at": toolkit.get("updated_at").isoformat() if toolkit.get("updated_at") else None,
            "last_synced_at": toolkit.get("last_synced_at").isoformat() if toolkit.get("last_synced_at") else None,
            "stats": {
                "total_tools": len(tools_data),
                "actions": len(actions),
                "triggers": len(triggers)
            },
            "tools": {
                "actions": actions,
                "triggers": triggers
            },
            "source": "database_fallback"
        }
        
        return provider
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching provider '{provider_slug}' from database: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch provider: {str(e)}"
        )
