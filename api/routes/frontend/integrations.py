"""
Frontend integrations routes.
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Import database configuration
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from database.config import get_database_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["Integrations"])

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
async def get_integrations(
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = 0
):
    """Get available integrations (toolkits) from the database with pagination support"""
    try:
        async with await get_database_session() as session:
            # Build base query for counting total
            count_query = """
                SELECT COUNT(*) as total
                FROM toolkits t
                WHERE t.is_deprecated = FALSE
            """
            
            # Build main query with optional search and pagination
            base_query = """
                SELECT 
                    t.toolkit_id,
                    t.slug,
                    t.name,
                    t.description,
                    t.logo_url,
                    t.category
                FROM toolkits t
                WHERE t.is_deprecated = FALSE
            """
            
            params = {}
            if search:
                search_condition = " AND (LOWER(t.name) LIKE LOWER(:search) OR LOWER(t.description) LIKE LOWER(:search))"
                count_query += search_condition
                base_query += search_condition
                params["search"] = f"%{search}%"
            
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
            
            integrations = []
            for row in rows:
                integration = {
                    "id": row.toolkit_id,
                    "slug": row.slug,
                    "name": row.name,
                    "description": row.description,
                    "logo": row.logo_url or f"/static/icons/{row.slug.lower()}.svg",  # Fallback to static icon
                    "category": row.category or "other"  # Default to "other" if no category
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
        async with await get_database_session() as session:
            # Build search query
            search_query = """
                SELECT 
                    t.toolkit_id,
                    t.slug,
                    t.name,
                    t.description,
                    t.logo_url,
                    t.category
                FROM toolkits t
                WHERE t.is_deprecated = FALSE
                AND (
                    LOWER(t.name) LIKE LOWER(:search) 
                    OR LOWER(t.description) LIKE LOWER(:search)
                    OR LOWER(t.slug) LIKE LOWER(:search)
                )
                ORDER BY 
                    CASE 
                        WHEN LOWER(t.name) LIKE LOWER(:exact_search) THEN 1
                        WHEN LOWER(t.name) LIKE LOWER(:search) THEN 2
                        ELSE 3
                    END,
                    t.name
                LIMIT :limit OFFSET :offset
            """
            
            params = {
                "search": f"%{q}%",
                "exact_search": f"{q}%",
                "limit": limit,
                "offset": offset
            }
            
            query = text(search_query)
            result = await session.execute(query, params)
            rows = result.fetchall()
            
            integrations = []
            for row in rows:
                integration = {
                    "id": row.toolkit_id,
                    "slug": row.slug,
                    "name": row.name,
                    "description": row.description,
                    "logo": row.logo_url or f"/static/icons/{row.slug.lower()}.svg",
                    "category": row.category or "other"
                }
                integrations.append(integration)
            
            return {
                "items": integrations,
                "query": q,
                "total": len(integrations),
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
        async with await get_database_session() as session:
            query = text("""
                SELECT 
                    t.toolkit_id,
                    t.slug,
                    t.name,
                    t.description,
                    t.logo_url,
                    t.category,
                    t.created_at,
                    t.updated_at
                FROM toolkits t
                WHERE t.slug = :slug AND t.is_deprecated = FALSE
            """)
            
            result = await session.execute(query, {"slug": slug})
            row = result.fetchone()
            
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Integration with slug '{slug}' not found"
                )
            
            integration = {
                "id": row.toolkit_id,
                "slug": row.slug,
                "name": row.name,
                "description": row.description,
                "logo": row.logo_url or f"/static/icons/{row.slug.lower()}.svg",
                "category": row.category or "other",
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None
            }
            
            return integration
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching integration by slug '{slug}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch integration: {str(e)}"
        )
