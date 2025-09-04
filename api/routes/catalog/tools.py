"""
Catalog tools routes.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["Catalog"])


async def _fallback_database_query(
    provider: Optional[str],
    search: Optional[str], 
    tool_type: Optional[str],
    limit: Optional[int],
    offset: Optional[int]
):
    """Fallback to direct database query when cache is not available"""
    try:
        from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
        from database.config import get_database_url
        
        # Create database connection
        database_url = get_database_url()
        client = AsyncIOMotorClient(database_url)
        database = client.get_database()
        
        # Build MongoDB query
        query = {"is_deprecated": False}
        
        # Add provider filter
        if provider:
            toolkit = await database.toolkits.find_one({
                "slug": provider,
                "is_deprecated": False
            })
            if toolkit:
                query["toolkit_id"] = toolkit["toolkit_id"]
            else:
                return {
                    "tools": [],
                    "pagination": {
                        "total": 0,
                        "limit": limit,
                        "offset": offset,
                        "has_more": False,
                        "page": 1,
                        "total_pages": 0
                    },
                    "filters": {
                        "provider": provider,
                        "search": search,
                        "tool_type": tool_type
                    },
                    "source": "database_fallback"
                }
        
        # Add tool type filter
        if tool_type:
            query["tool_type"] = tool_type
        
        # Add search filter
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        
        # Get total count
        total_count = await database.tools.count_documents(query)
        
        # Get tools with pagination
        cursor = database.tools.find(query).sort([
            ("toolkit_id", 1),
            ("tool_type", 1),
            ("name", 1)
        ])
        
        if offset:
            cursor = cursor.skip(offset)
        if limit:
            cursor = cursor.limit(limit)
        
        tools_data = await cursor.to_list(length=None)
        
        # Get toolkit information for each tool
        tools = []
        for tool in tools_data:
            toolkit = await database.toolkits.find_one({
                "_id": tool["toolkit_id"]
            })
            
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
                "tags": tool.get("tags", []),
                "toolkit": {
                    "slug": toolkit["slug"] if toolkit else None,
                    "name": toolkit["name"] if toolkit else None,
                    "category": toolkit.get("category") if toolkit else None
                }
            }
            tools.append(tool_info)
        
        # Close database connection
        client.close()
        
        return {
            "tools": tools,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": limit and (offset + limit) < total_count,
                "page": (offset // limit) + 1 if limit else 1,
                "total_pages": (total_count + limit - 1) // limit if limit else 1
            },
            "filters": {
                "provider": provider,
                "search": search,
                "tool_type": tool_type
            },
            "source": "database_fallback"
        }
        
    except Exception as e:
        logger.error(f"Error in fallback database query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch tools: {str(e)}"
        )

@router.get("")
async def list_tools(
    provider: Optional[str] = Query(None, description="Filter by toolkit slug"),
    search: Optional[str] = Query(None, description="Search term for tool names and descriptions"),
    tool_type: Optional[str] = Query(None, description="Filter by tool type: 'action' or 'trigger'"),
    limit: Optional[int] = Query(100, ge=1, le=1000, description="Number of tools to return"),
    offset: Optional[int] = Query(0, ge=0, description="Number of tools to skip")
):
    """List tools with optional filtering and pagination using cached data"""
    try:
        # Get the global cache service
        from api.cache_service import get_global_cache_service
        cache_service = await get_global_cache_service()
        
        if not cache_service.is_initialized():
            logger.warning("Cache service not initialized, attempting to initialize")
            await cache_service.initialize()
        
        # Get cached catalog data
        catalog_cache = cache_service.get_catalog_cache()
        
        if not catalog_cache:
            logger.warning("No catalog cache available, falling back to direct database query")
            # Fallback to direct database query if cache is not available
            return await _fallback_database_query(provider, search, tool_type, limit, offset)
        
        # Extract all tools from cached providers
        all_tools = []
        for provider_slug, provider_data in catalog_cache.items():
            # Skip if provider filter is specified and doesn't match
            if provider and provider_slug != provider:
                continue
                
            # Get actions and triggers from this provider
            actions = provider_data.get('actions', [])
            triggers = provider_data.get('triggers', [])
            
            # Add provider info to each tool
            for action in actions:
                action['toolkit'] = {
                    'slug': provider_slug,
                    'name': provider_data.get('name', provider_slug),
                    'category': provider_data.get('category')
                }
                all_tools.append(action)
            
            for trigger in triggers:
                trigger['toolkit'] = {
                    'slug': provider_slug,
                    'name': provider_data.get('name', provider_slug),
                    'category': provider_data.get('category')
                }
                all_tools.append(trigger)
        
        # Apply filters
        filtered_tools = all_tools
        
        # Apply tool type filter
        if tool_type:
            filtered_tools = [tool for tool in filtered_tools if tool.get('type') == tool_type]
        
        # Apply search filter
        if search:
            search_lower = search.lower()
            filtered_tools = [
                tool for tool in filtered_tools
                if (search_lower in tool.get('name', '').lower() or
                    search_lower in tool.get('description', '').lower())
            ]
        
        # Sort tools
        filtered_tools.sort(key=lambda x: (
            x.get('toolkit', {}).get('slug', ''),
            x.get('type', ''),
            x.get('name', '')
        ))
        
        # Apply pagination
        total_count = len(filtered_tools)
        paginated_tools = filtered_tools[offset:offset + limit] if limit else filtered_tools[offset:]
        
        return {
            "tools": paginated_tools,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": limit and (offset + limit) < total_count,
                "page": (offset // limit) + 1 if limit else 1,
                "total_pages": (total_count + limit - 1) // limit if limit else 1
            },
            "filters": {
                "provider": provider,
                "search": search,
                "tool_type": tool_type
            },
            "source": "cache"
        }
        
    except Exception as e:
        logger.error(f"Error fetching tools from cache: {e}")
        # Fallback to database query
        return await _fallback_database_query(provider, search, tool_type, limit, offset)

@router.get("/{tool_name}")
async def get_tool(tool_name: str):
    """Get tool information by name using cached data"""
    try:
        # Get the global cache service
        from api.cache_service import get_global_cache_service
        cache_service = await get_global_cache_service()
        
        if not cache_service.is_initialized():
            logger.warning("Cache service not initialized, attempting to initialize")
            await cache_service.initialize()
        
        # Get cached catalog data
        catalog_cache = cache_service.get_catalog_cache()
        
        if not catalog_cache:
            logger.warning("No catalog cache available, falling back to direct database query")
            return await _fallback_get_tool_database(tool_name)
        
        # Search for tool in cached data
        for provider_slug, provider_data in catalog_cache.items():
            # Check actions
            for action in provider_data.get('actions', []):
                if action.get('slug') == tool_name or action.get('name') == tool_name:
                    action['toolkit'] = {
                        'slug': provider_slug,
                        'name': provider_data.get('name', provider_slug),
                        'category': provider_data.get('category'),
                        'description': provider_data.get('description'),
                        'logo_url': provider_data.get('logo_url'),
                        'website_url': provider_data.get('website_url')
                    }
                    return {**action, "source": "cache"}
            
            # Check triggers
            for trigger in provider_data.get('triggers', []):
                if trigger.get('slug') == tool_name or trigger.get('name') == tool_name:
                    trigger['toolkit'] = {
                        'slug': provider_slug,
                        'name': provider_data.get('name', provider_slug),
                        'category': provider_data.get('category'),
                        'description': provider_data.get('description'),
                        'logo_url': provider_data.get('logo_url'),
                        'website_url': provider_data.get('website_url')
                    }
                    return {**trigger, "source": "cache"}
        
        # Tool not found in cache, try database fallback
        return await _fallback_get_tool_database(tool_name)
        
    except Exception as e:
        logger.error(f"Error fetching tool '{tool_name}' from cache: {e}")
        # Fallback to database query
        return await _fallback_get_tool_database(tool_name)

async def _fallback_get_tool_database(tool_name: str):
    """Fallback to direct database query for individual tool"""
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from database.config import get_database_url
        
        # Create database connection
        database_url = get_database_url()
        client = AsyncIOMotorClient(database_url)
        database = client.get_database()
        
        # Find tool by slug or name
        tool = await database.tools.find_one({
            "$or": [
                {"slug": tool_name, "is_deprecated": False},
                {"name": tool_name, "is_deprecated": False}
            ]
        })
        
        if not tool:
            client.close()
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{tool_name}' not found"
            )
        
        # Get toolkit information
        toolkit = await database.toolkits.find_one({
            "_id": tool["toolkit_id"]
        })
        
        # Close database connection
        client.close()
        
        # Build response
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
            "tags": tool.get("tags", []),
            "toolkit": {
                "id": str(toolkit["_id"]) if toolkit else None,
                "slug": toolkit["slug"] if toolkit else None,
                "name": toolkit["name"] if toolkit else None,
                "description": toolkit.get("description") if toolkit else None,
                "category": toolkit.get("category") if toolkit else None,
                "logo_url": toolkit.get("logo_url") if toolkit else None,
                "website_url": toolkit.get("website_url") if toolkit else None
            } if toolkit else None,
            "source": "database_fallback"
        }
        
        return tool_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tool '{tool_name}' from database: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch tool: {str(e)}"
        )