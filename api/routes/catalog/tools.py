"""
Catalog tools routes.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
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

router = APIRouter(prefix="/tools", tags=["Catalog"])

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

@router.get("")
async def list_tools(
    provider: Optional[str] = Query(None, description="Filter by toolkit slug"),
    search: Optional[str] = Query(None, description="Search term for tool names and descriptions"),
    tool_type: Optional[str] = Query(None, description="Filter by tool type: 'action' or 'trigger'"),
    limit: Optional[int] = Query(100, ge=1, le=1000, description="Number of tools to return"),
    offset: Optional[int] = Query(0, ge=0, description="Number of tools to skip")
):
    """List tools with optional filtering and pagination"""
    try:
        async with await get_database_session() as session:
            # Build base query for counting total
            count_query = """
                SELECT COUNT(*) as total
                FROM tools t
                JOIN toolkits tk ON t.toolkit_id = tk.toolkit_id
                WHERE t.is_deprecated = FALSE AND tk.is_deprecated = FALSE
            """
            
            # Build main query
            base_query = """
                SELECT 
                    t.tool_id,
                    t.slug,
                    t.name,
                    t.display_name,
                    t.description,
                    t.tool_type,
                    t.version,
                    t.input_schema,
                    t.output_schema,
                    t.tags,
                    tk.slug as toolkit_slug,
                    tk.name as toolkit_name,
                    tk.category as toolkit_category
                FROM tools t
                JOIN toolkits tk ON t.toolkit_id = tk.toolkit_id
                WHERE t.is_deprecated = FALSE AND tk.is_deprecated = FALSE
            """
            
            params = {}
            conditions = []
            
            # Add provider filter
            if provider:
                provider_condition = " AND tk.slug = :provider"
                count_query += provider_condition
                base_query += provider_condition
                params["provider"] = provider
            
            # Add search filter
            if search:
                search_condition = " AND (LOWER(t.name) LIKE LOWER(:search) OR LOWER(t.description) LIKE LOWER(:search))"
                count_query += search_condition
                base_query += search_condition
                params["search"] = f"%{search}%"
            
            # Add tool type filter
            if tool_type:
                type_condition = " AND t.tool_type = :tool_type"
                count_query += type_condition
                base_query += type_condition
                params["tool_type"] = tool_type
            
            # Get total count
            count_result = await session.execute(text(count_query), params)
            total_count = count_result.scalar()
            
            # Add ordering and pagination
            base_query += " ORDER BY tk.name, t.tool_type, t.name"
            if limit:
                base_query += " LIMIT :limit OFFSET :offset"
                params["limit"] = limit
                params["offset"] = offset
            
            query = text(base_query)
            result = await session.execute(query, params)
            rows = result.fetchall()
            
            tools = []
            for row in rows:
                tool = {
                    "id": row.tool_id,
                    "slug": row.slug,
                    "name": row.name,
                    "display_name": row.display_name,
                    "description": row.description,
                    "type": row.tool_type,
                    "version": row.version,
                    "input_schema": row.input_schema,
                    "output_schema": row.output_schema,
                    "tags": row.tags or [],
                    "toolkit": {
                        "slug": row.toolkit_slug,
                        "name": row.toolkit_name,
                        "category": row.toolkit_category
                    }
                }
                tools.append(tool)
            
            return {
                "items": tools,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": limit and (offset + limit) < total_count
                },
                "filters": {
                    "provider": provider,
                    "search": search,
                    "tool_type": tool_type
                }
            }
            
    except Exception as e:
        logger.error(f"Error fetching tools from database: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch tools from database: {str(e)}"
        )

@router.get("/{tool_name}")
async def get_tool(tool_name: str):
    """Get tool information by name"""
    try:
        async with await get_database_session() as session:
            query = text("""
                SELECT 
                    t.tool_id,
                    t.slug,
                    t.name,
                    t.display_name,
                    t.description,
                    t.tool_type,
                    t.version,
                    t.input_schema,
                    t.output_schema,
                    t.tags,
                    tk.slug as toolkit_slug,
                    tk.name as toolkit_name,
                    tk.category as toolkit_category,
                    tk.description as toolkit_description,
                    tk.website_url as toolkit_website
                FROM tools t
                JOIN toolkits tk ON t.toolkit_id = tk.toolkit_id
                WHERE t.slug = :tool_name 
                AND t.is_deprecated = FALSE 
                AND tk.is_deprecated = FALSE
            """)
            
            result = await session.execute(query, {"tool_name": tool_name})
            row = result.fetchone()
            
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tool '{tool_name}' not found"
                )
            
            tool = {
                "id": row.tool_id,
                "slug": row.slug,
                "name": row.name,
                "display_name": row.display_name,
                "description": row.description,
                "type": row.tool_type,
                "version": row.version,
                "input_schema": row.input_schema,
                "output_schema": row.output_schema,
                "tags": row.tags or [],
                "toolkit": {
                    "slug": row.toolkit_slug,
                    "name": row.toolkit_name,
                    "category": row.toolkit_category,
                    "description": row.toolkit_description,
                    "website": row.toolkit_website
                }
            }
            
            return tool
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tool '{tool_name}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch tool: {str(e)}"
        )
