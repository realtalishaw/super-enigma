"""
API routes for semantic search functionality.
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from core.semantic_search.search_service import SemanticSearchService

logger = logging.getLogger(__name__)

# Create router
semantic_router = APIRouter(prefix="/semantic-search", tags=["semantic-search"])

# Global search service instance
_search_service: Optional[SemanticSearchService] = None

def get_search_service() -> SemanticSearchService:
    """Get or create the semantic search service."""
    global _search_service
    if _search_service is None:
        # Initialize with default paths
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent.parent
        index_path = project_root / "data" / "semantic_index"
        
        _search_service = SemanticSearchService(
            embedding_model="all-MiniLM-L6-v2",
            index_path=index_path
        )
        
        # Check if index exists
        if not index_path.exists():
            logger.warning("Semantic search index not found. Please build it first using scripts/build_semantic_index.py")
    
    return _search_service

# Request/Response models
class SearchRequest(BaseModel):
    query: str
    k: int = 10
    filter_types: Optional[List[str]] = None
    filter_categories: Optional[List[str]] = None
    filter_providers: Optional[List[str]] = None

class SearchResult(BaseModel):
    item: Dict[str, Any]
    similarity_score: float
    rank: int

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_results: int
    index_stats: Dict[str, Any]

class SimilarToolsRequest(BaseModel):
    tool_item: Dict[str, Any]
    k: int = 5
    exclude_self: bool = True

class IndexStatsResponse(BaseModel):
    faiss_stats: Dict[str, Any]
    embedding_model: Dict[str, Any]
    index_path: Optional[str]

@semantic_router.post("/search", response_model=SearchResponse)
async def semantic_search(
    request: SearchRequest,
    search_service: SemanticSearchService = Depends(get_search_service)
):
    """
    Perform semantic search over the tool catalog.
    """
    try:
        # Perform search
        results = search_service.search(
            query=request.query,
            k=request.k,
            filter_types=request.filter_types,
            filter_categories=request.filter_categories,
            filter_providers=request.filter_providers
        )
        
        # Convert to response format
        search_results = [
            SearchResult(
                item=result["item"],
                similarity_score=result["similarity_score"],
                rank=result["rank"]
            )
            for result in results
        ]
        
        # Get index stats
        index_stats = search_service.get_index_stats()
        
        return SearchResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results),
            index_stats=index_stats
        )
        
    except Exception as e:
        logger.error(f"Error in semantic search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@semantic_router.get("/search", response_model=SearchResponse)
async def semantic_search_get(
    query: str = Query(..., description="Search query"),
    k: int = Query(10, ge=1, le=50, description="Number of results to return"),
    filter_types: Optional[str] = Query(None, description="Comma-separated list of types to filter by"),
    filter_categories: Optional[str] = Query(None, description="Comma-separated list of categories to filter by"),
    filter_providers: Optional[str] = Query(None, description="Comma-separated list of providers to filter by"),
    search_service: SemanticSearchService = Depends(get_search_service)
):
    """
    Perform semantic search over the tool catalog (GET version).
    """
    try:
        # Parse filter parameters
        filter_types_list = filter_types.split(",") if filter_types else None
        filter_categories_list = filter_categories.split(",") if filter_categories else None
        filter_providers_list = filter_providers.split(",") if filter_providers else None
        
        # Perform search
        results = search_service.search(
            query=query,
            k=k,
            filter_types=filter_types_list,
            filter_categories=filter_categories_list,
            filter_providers=filter_providers_list
        )
        
        # Convert to response format
        search_results = [
            SearchResult(
                item=result["item"],
                similarity_score=result["similarity_score"],
                rank=result["rank"]
            )
            for result in results
        ]
        
        # Get index stats
        index_stats = search_service.get_index_stats()
        
        return SearchResponse(
            query=query,
            results=search_results,
            total_results=len(search_results),
            index_stats=index_stats
        )
        
    except Exception as e:
        logger.error(f"Error in semantic search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@semantic_router.post("/similar-tools", response_model=List[SearchResult])
async def find_similar_tools(
    request: SimilarToolsRequest,
    search_service: SemanticSearchService = Depends(get_search_service)
):
    """
    Find tools similar to a given tool.
    """
    try:
        # Find similar tools
        results = search_service.search_similar_tools(
            tool_item=request.tool_item,
            k=request.k,
            exclude_self=request.exclude_self
        )
        
        # Convert to response format
        search_results = [
            SearchResult(
                item=result["item"],
                similarity_score=result["similarity_score"],
                rank=result["rank"]
            )
            for result in results
        ]
        
        return search_results
        
    except Exception as e:
        logger.error(f"Error finding similar tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@semantic_router.get("/stats", response_model=IndexStatsResponse)
async def get_index_stats(
    search_service: SemanticSearchService = Depends(get_search_service)
):
    """
    Get statistics about the semantic search index.
    """
    try:
        stats = search_service.get_index_stats()
        return IndexStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Error getting index stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@semantic_router.post("/rebuild")
async def rebuild_index(
    search_service: SemanticSearchService = Depends(get_search_service)
):
    """
    Rebuild the semantic search index from the catalog data.
    """
    try:
        # Load catalog data
        from pathlib import Path
        import json
        
        project_root = Path(__file__).parent.parent.parent.parent
        catalog_path = project_root / "catalog.json"
        
        if not catalog_path.exists():
            raise HTTPException(status_code=404, detail="Catalog file not found")
        
        with open(catalog_path, 'r') as f:
            catalog_data = json.load(f)
        
        # Rebuild index
        search_service.rebuild_index(catalog_data)
        
        # Get updated stats
        stats = search_service.get_index_stats()
        
        return {
            "message": "Index rebuilt successfully",
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error rebuilding index: {e}")
        raise HTTPException(status_code=500, detail=str(e))
