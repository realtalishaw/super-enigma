"""
Catalog routes package.
"""

from api.routes.catalog.providers import router as providers_router
from api.routes.catalog.tools import router as tools_router

# Create a combined catalog router
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Import database configuration
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from database.config import get_database_url

logger = logging.getLogger(__name__)

catalog_router = APIRouter(prefix="/catalog", tags=["Catalog"])

# Include all catalog sub-routers
catalog_router.include_router(providers_router)
catalog_router.include_router(tools_router)

# Database engine and session factory
_engine = None
_session_factory = None

async def get_database_session() -> AsyncSession:
    """Get database session"""
    global _engine, _session_factory
    
    if _engine is None:
        database_url = get_database_url()
        # Convert to async URL
        async_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
        _engine = create_async_engine(async_url, echo=False)
        _session_factory = sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
    
    return _session_factory()

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
    Get the complete tool catalog with pagination.
    
    Returns toolkits with their associated tools (actions and triggers).
    Supports filtering by category, search terms, and tool availability.
    """
    try:
        async with await get_database_session() as session:
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
            conditions = []
            
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
            
            # Add ordering (GROUP BY is already in the base query)
            
            # Get total count
            count_result = await session.execute(text(count_query), params)
            total_count = count_result.scalar()
            
            # Add ordering and pagination to main query
            base_query += " ORDER BY t.name"
            if limit:
                base_query += " LIMIT :limit OFFSET :offset"
                params["limit"] = limit
                params["offset"] = offset
            
            query = text(base_query)
            result = await session.execute(query, params)
            rows = result.fetchall()
            
            # Process results and get detailed tool information
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
                }
            }
            
    except Exception as e:
        logger.error(f"Error fetching catalog from database: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch catalog from database: {str(e)}"
        )

@catalog_router.get("/categories")
async def get_categories():
    """Get all available toolkit categories"""
    try:
        async with await get_database_session() as session:
            # Get unique categories from toolkits table since toolkit_categories doesn't have display_order
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
                "total": len(categories)
            }
            
    except Exception as e:
        logger.error(f"Error fetching categories from database: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch categories from database: {str(e)}"
        )

__all__ = [
    "catalog_router",
    "providers_router",
    "tools_router"
]
