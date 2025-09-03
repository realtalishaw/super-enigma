"""
Catalog routes package.
"""

from api.routes.catalog.providers import router as providers_router
from api.routes.catalog.tools import router as tools_router

# Create a combined catalog router
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

catalog_router = APIRouter(prefix="/catalog", tags=["Catalog"])

# Include all catalog sub-routers
catalog_router.include_router(providers_router)
catalog_router.include_router(tools_router)

async def get_global_cache_service():
    """Get the global cache service instance"""
    from api.cache_service import get_global_cache_service
    return await get_global_cache_service()

@catalog_router.get("")
async def get_catalog(
    search: Optional[str] = Query(None, description="Search term for toolkit names and descriptions"),
    category: Optional[str] = Query(None, description="Filter by toolkit category"),
    has_actions: Optional[bool] = Query(None, description="Filter toolkits that have actions"),
    has_triggers: Optional[bool] = Query(None, description="Filter toolkits that have triggers"),
    limit: Optional[int] = Query(20, ge=1, le=100, description="Number of toolkits to return"),
    offset: Optional[int] = Query(0, ge=0, description="Number of toolkits to skip")
):
    """
    Get the complete tool catalog with pagination using cached data.
    
    Returns toolkits with their associated tools (actions and triggers).
    Supports filtering by category, search terms, and tool availability.
    """
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
            return await _fallback_get_catalog_database(search, category, has_actions, has_triggers, limit, offset)
        
        # Convert cached data to catalog items
        catalog_items = []
        for provider_slug, provider_data in catalog_cache.items():
            actions = provider_data.get('actions', [])
            triggers = provider_data.get('triggers', [])
            
            # Apply filters
            if category and provider_data.get('category') != category:
                continue
            
            if search:
                search_lower = search.lower()
                if (search_lower not in provider_data.get('name', '').lower() and
                    search_lower not in provider_data.get('description', '').lower()):
                    continue
            
            if has_actions is not None:
                if has_actions and not actions:
                    continue
                if not has_actions and actions:
                    continue
            
            if has_triggers is not None:
                if has_triggers and not triggers:
                    continue
                if not has_triggers and triggers:
                    continue
            
            # Create toolkit entry
            toolkit = {
                "id": provider_data.get('id'),
                "slug": provider_slug,
                "name": provider_data.get('name', provider_slug),
                "description": provider_data.get('description'),
                "icon_url": provider_data.get('logo_url'),
                "website_url": provider_data.get('website_url'),
                "category": provider_data.get('category'),
                "version": provider_data.get('version'),
                "created_at": provider_data.get('created_at'),
                "updated_at": provider_data.get('updated_at'),
                "stats": {
                    "total_tools": len(actions) + len(triggers),
                    "actions": len(actions),
                    "triggers": len(triggers)
                },
                "tools": {
                    "actions": actions,
                    "triggers": triggers
                }
            }
            
            catalog_items.append(toolkit)
        
        # Sort by name
        catalog_items.sort(key=lambda x: x['name'])
        
        # Apply pagination
        total_count = len(catalog_items)
        paginated_items = catalog_items[offset:offset + limit] if limit else catalog_items[offset:]
        
        return {
            "items": paginated_items,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": limit and (offset + limit) < total_count,
                "page": (offset // limit) + 1 if limit else 1,
                "total_pages": (total_count + limit - 1) // limit if limit else 1
            },
            "filters": {
                "search": search,
                "category": category,
                "has_actions": has_actions,
                "has_triggers": has_triggers
            },
            "summary": {
                "total_toolkits": len(paginated_items),
                "total_tools": sum(item["stats"]["total_tools"] for item in paginated_items),
                "total_actions": sum(item["stats"]["actions"] for item in paginated_items),
                "total_triggers": sum(item["stats"]["triggers"] for item in paginated_items)
            },
            "source": "cache"
        }
        
    except Exception as e:
        logger.error(f"Error fetching catalog from cache: {e}")
        # Fallback to database query
        return await _fallback_get_catalog_database(search, category, has_actions, has_triggers, limit, offset)

async def _fallback_get_catalog_database(
    search: Optional[str],
    category: Optional[str],
    has_actions: Optional[bool],
    has_triggers: Optional[bool],
    limit: Optional[int],
    offset: Optional[int]
):
    """Fallback to direct database query when cache is not available"""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import text
        from database.config import get_database_url
        
        # Create database connection
        database_url = get_database_url()
        async_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
        engine = create_async_engine(async_url, echo=False)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with session_factory() as session:
            # Build base query for counting total
            count_query = """
                SELECT COUNT(DISTINCT t.toolkit_id) as total
                FROM toolkits t
                WHERE t.is_deprecated = FALSE
            """
            
            # Build main query with joins to get toolkit and tool information
            base_query = """
                SELECT 
                    t.toolkit_id,
                    t.slug,
                    t.name,
                    t.description,
                    t.logo_url as icon_url,
                    t.website_url,
                    t.category,
                    t.version,
                    t.created_at,
                    t.updated_at,
                    COUNT(DISTINCT tools.tool_id) as tool_count,
                    COUNT(DISTINCT CASE WHEN tools.tool_type = 'action' THEN tools.tool_id END) as action_count,
                    COUNT(DISTINCT CASE WHEN tools.tool_type = 'trigger' THEN tools.tool_id END) as trigger_count
                FROM toolkits t
                LEFT JOIN tools ON t.toolkit_id = tools.toolkit_id AND tools.is_deprecated = FALSE
                WHERE t.is_deprecated = FALSE
                GROUP BY t.toolkit_id, t.slug, t.name, t.description, t.logo_url, t.website_url, t.category, t.version, t.created_at, t.updated_at
            """
            
            params = {}
            
            # Add search filter
            if search:
                search_condition = " AND (LOWER(t.name) LIKE LOWER(:search) OR LOWER(t.description) LIKE LOWER(:search))"
                count_query += search_condition
                base_query += search_condition
                params["search"] = f"%{search}%"
            
            # Add category filter
            if category:
                category_condition = " AND t.category = :category"
                count_query += category_condition
                base_query += category_condition
                params["category"] = category
            
            # Get total count
            count_result = await session.execute(text(count_query), params)
            total_count = count_result.scalar()
            
            # Add ordering and pagination
            base_query += " ORDER BY t.name"
            if limit:
                base_query += " LIMIT :limit OFFSET :offset"
                params["limit"] = limit
                params["offset"] = offset
            
            # Execute main query
            result = await session.execute(text(base_query), params)
            rows = result.fetchall()
            
            catalog_items = []
            for row in rows:
                # Get detailed tools for this toolkit
                tools_query = text("""
                    SELECT 
                        tool_id,
                        slug,
                        name,
                        display_name,
                        description,
                        tool_type,
                        version,
                        input_schema,
                        output_schema,
                        tags
                    FROM tools 
                    WHERE toolkit_id = :toolkit_id AND is_deprecated = FALSE
                    ORDER BY tool_type, name
                """)
                
                tools_result = await session.execute(tools_query, {"toolkit_id": row.toolkit_id})
                tools_data = tools_result.fetchall()
                
                # Organize tools by type
                actions = []
                triggers = []
                
                for tool_row in tools_data:
                    tool = {
                        "id": tool_row.tool_id,
                        "slug": tool_row.slug,
                        "name": tool_row.name,
                        "display_name": tool_row.display_name,
                        "description": tool_row.description,
                        "type": tool_row.tool_type,
                        "version": tool_row.version,
                        "input_schema": tool_row.input_schema,
                        "output_schema": tool_row.output_schema,
                        "tags": tool_row.tags or []
                    }
                    
                    if tool_row.tool_type == 'action':
                        actions.append(tool)
                    elif tool_row.tool_type == 'trigger':
                        triggers.append(tool)
                
                # Create toolkit entry
                toolkit = {
                    "id": row.toolkit_id,
                    "slug": row.slug,
                    "name": row.name,
                    "description": row.description,
                    "icon_url": row.icon_url,
                    "website_url": row.website_url,
                    "category": row.category,
                    "version": row.version,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    "stats": {
                        "total_tools": row.tool_count,
                        "actions": row.action_count,
                        "triggers": row.trigger_count
                    },
                    "tools": {
                        "actions": actions,
                        "triggers": triggers
                    }
                }
                
                # Apply tool availability filters
                if has_actions is not None and row.action_count > 0 != has_actions:
                    continue
                if has_triggers is not None and row.trigger_count > 0 != has_triggers:
                    continue
                
                catalog_items.append(toolkit)
            
            return {
                "items": catalog_items,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": limit and (offset + limit) < total_count,
                    "page": (offset // limit) + 1 if limit else 1,
                    "total_pages": (total_count + limit - 1) // limit if limit else 1
                },
                "filters": {
                    "search": search,
                    "category": category,
                    "has_actions": has_actions,
                    "has_triggers": has_triggers
                },
                "summary": {
                    "total_toolkits": len(catalog_items),
                    "total_tools": sum(item["stats"]["total_tools"] for item in catalog_items),
                    "total_actions": sum(item["stats"]["actions"] for item in catalog_items),
                    "total_triggers": sum(item["stats"]["triggers"] for item in catalog_items)
                },
                "source": "database_fallback"
            }
        
    except Exception as e:
        logger.error(f"Error in fallback catalog database query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch catalog: {str(e)}"
        )

@catalog_router.get("/categories")
async def get_categories():
    """Get all available toolkit categories using cached data"""
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
            return await _fallback_get_categories_database()
        
        # Extract categories from cached data
        categories_dict = {}
        for provider_slug, provider_data in catalog_cache.items():
            category = provider_data.get('category')
            if category:
                if category not in categories_dict:
                    categories_dict[category] = 0
                categories_dict[category] += 1
        
        # Convert to list and sort by count
        categories = [
            {
                "slug": category,
                "name": category,
                "toolkit_count": count
            }
            for category, count in categories_dict.items()
        ]
        categories.sort(key=lambda x: x['toolkit_count'], reverse=True)
        
        return {
            "categories": categories,
            "total": len(categories),
            "source": "cache"
        }
        
    except Exception as e:
        logger.error(f"Error fetching categories from cache: {e}")
        # Fallback to database query
        return await _fallback_get_categories_database()

async def _fallback_get_categories_database():
    """Fallback to direct database query for categories"""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import text
        from database.config import get_database_url
        
        # Create database connection
        database_url = get_database_url()
        async_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
        engine = create_async_engine(async_url, echo=False)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with session_factory() as session:
            # Get unique categories from toolkits table
            query = text("""
                SELECT 
                    category as slug,
                    category as name,
                    COUNT(*) as toolkit_count
                FROM toolkits
                WHERE is_deprecated = FALSE
                GROUP BY category
                ORDER BY toolkit_count DESC, category
            """)
            
            result = await session.execute(query)
            categories = []
            
            for row in result.fetchall():
                category = {
                    "slug": row.slug,
                    "name": row.name,
                    "toolkit_count": row.toolkit_count
                }
                categories.append(category)
            
            return {
                "categories": categories,
                "total": len(categories),
                "source": "database_fallback"
            }
        
    except Exception as e:
        logger.error(f"Error in fallback categories database query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch categories: {str(e)}"
        )

__all__ = [
    "catalog_router",
    "providers_router",
    "tools_router"
]