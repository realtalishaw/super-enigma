"""
Catalog providers routes.
"""

from fastapi import APIRouter, HTTPException
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

router = APIRouter(prefix="/providers", tags=["Catalog"])

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

@router.get("/{provider_slug}")
async def get_provider(provider_slug: str):
    """Get toolkit information by slug with all associated tools"""
    try:
        async with await get_database_session() as session:
            # Get toolkit information
            toolkit_query = text("""
                SELECT 
                    toolkit_id,
                    slug,
                    name,
                    description,
                    logo_url,
                    website_url,
                    category,
                    version,
                    created_at,
                    updated_at,
                    last_synced_at
                FROM toolkits
                WHERE slug = :provider_slug AND is_deprecated = FALSE
            """)
            
            toolkit_result = await session.execute(toolkit_query, {"provider_slug": provider_slug})
            toolkit_row = toolkit_result.fetchone()
            
            if not toolkit_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Provider '{provider_slug}' not found"
                )
            
            # Get tools for this toolkit
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
            
            tools_result = await session.execute(tools_query, {"toolkit_id": toolkit_row.toolkit_id})
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
            
            # Build provider response
            provider = {
                "id": toolkit_row.toolkit_id,
                "slug": toolkit_row.slug,
                "name": toolkit_row.name,
                "description": toolkit_row.description,
                "logo_url": toolkit_row.logo_url,
                "website_url": toolkit_row.website_url,
                "category": toolkit_row.category,
                "version": toolkit_row.version,
                "created_at": toolkit_row.created_at.isoformat() if toolkit_row.created_at else None,
                "updated_at": toolkit_row.updated_at.isoformat() if toolkit_row.updated_at else None,
                "last_synced_at": toolkit_row.last_synced_at.isoformat() if toolkit_row.last_synced_at else None,
                "stats": {
                    "total_tools": len(tools_data),
                    "actions": len(actions),
                    "triggers": len(triggers)
                },
                "tools": {
                    "actions": actions,
                    "triggers": triggers
                }
            }
            
            return provider
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching provider '{provider_slug}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch provider: {str(e)}"
        )
