"""
Catalog tools routes.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bson import ObjectId

# Import database configuration
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from database.config import get_database_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["Catalog"])

# Global MongoDB client
_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None

async def get_database():
    """Get MongoDB database instance"""
    global _client, _database
    
    if _client is None:
        database_url = get_database_url()
        _client = AsyncIOMotorClient(database_url)
        _database = _client.get_database()
    
    return _database

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
        database = await get_database()
        
        # Build MongoDB query
        query = {
            "is_deprecated": False
        }
        
        # Add provider filter
        if provider:
            # First get the toolkit_id for the provider slug
            toolkit = await database.toolkits.find_one({
                "slug": provider,
                "is_deprecated": False
            })
            if toolkit:
                query["toolkit_id"] = toolkit["toolkit_id"]
            else:
                # Provider not found, return empty results
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
                    }
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
            # Get toolkit info
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
        database = await get_database()
        
        # Find tool by name
        tool = await database.tools.find_one({
            "name": tool_name,
            "is_deprecated": False
        })
        
        if not tool:
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{tool_name}' not found"
            )
        
        # Get toolkit information
        toolkit = await database.toolkits.find_one({
            "_id": tool["toolkit_id"]
        })
        
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
            } if toolkit else None
        }
        
        return tool_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tool '{tool_name}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch tool: {str(e)}"
        )