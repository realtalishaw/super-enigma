"""
Semantic search service that combines embedding generation and FAISS indexing.
"""

import logging
import json
import asyncio
from typing import List, Dict, Any, Optional, Union, Tuple
from pathlib import Path
import numpy as np

from .embedding_service import EmbeddingService
from .faiss_index import FAISSIndex
from core.catalog.database_service import DatabaseCatalogService
from core.catalog.cache import RedisCacheStore
from core.catalog.redis_client import RedisClientFactory
from core.config import settings

logger = logging.getLogger(__name__)

class SemanticSearchService:
    """
    High-level semantic search service for the tool catalog.
    """
    
    def __init__(
        self, 
        embedding_model: str = "all-MiniLM-L6-v2",
        index_path: Optional[Union[str, Path]] = None,
        device: Optional[str] = None
    ):
        """
        Initialize the semantic search service.
        
        Args:
            embedding_model: Name of the sentence-transformer model
            index_path: Path to save/load the FAISS index
            device: Device to run the model on
        """
        self.index_path = Path(index_path) if index_path else None
        
        # Initialize embedding service
        self.embedding_service = EmbeddingService(embedding_model, device)
        
        # Initialize FAISS index
        self.faiss_index = FAISSIndex(
            embedding_dim=self.embedding_service.get_embedding_dimension(),
            index_type="flat",
            metric="cosine"
        )
        
        # Load existing index if available
        if self.index_path and Path(f"{self.index_path}.faiss").exists():
            self._load_index()
        
        logger.info("Semantic search service initialized")
    
    def build_index_from_catalog(self, catalog_data: Dict[str, Any]) -> None:
        """
        Build the FAISS index from catalog data.
        
        Args:
            catalog_data: Dictionary containing the full catalog data
        """
        logger.info("Building FAISS index from catalog data")
        
        # Extract all catalog items
        catalog_items = self._extract_catalog_items(catalog_data)
        
        if not catalog_items:
            logger.warning("No catalog items found to index")
            return
        
        # Generate embeddings for all items
        logger.info(f"Generating embeddings for {len(catalog_items)} catalog items")
        embeddings = self.embedding_service.embed_catalog_items(catalog_items)
        
        # Add to FAISS index
        self.faiss_index.add_vectors(embeddings, catalog_items)
        
        # Save the index
        if self.index_path:
            self._save_index()
        
        logger.info(f"Index built successfully with {self.faiss_index.get_vector_count()} vectors")
    
    async def build_index_from_database(self) -> None:
        """Build the FAISS index from database catalog data."""
        logger.info("Building semantic search index from database...")
        
        try:
            # Initialize database service
            redis_client = await RedisClientFactory.get_client()
            cache_store = RedisCacheStore(redis_client)
            catalog_service = DatabaseCatalogService(settings.database_url, cache_store)
            
            # Get complete catalog data from database
            logger.info("Fetching complete catalog from database...")
            catalog_response = await catalog_service.get_catalog()
            
            if not catalog_response or "providers" not in catalog_response:
                logger.error("Failed to fetch catalog from database")
                return
            
            # Extract all catalog items (providers, tools, actions, triggers)
            items = self._extract_database_catalog_items(catalog_response["providers"])
            
            if not items:
                logger.warning("No catalog items found to index")
                return
            
            # Generate embeddings for all items
            logger.info(f"Generating embeddings for {len(items)} items...")
            embeddings = self.embedding_service.embed_catalog_items(items)
            
            if embeddings is None or len(embeddings) == 0:
                logger.error("Failed to generate embeddings")
                return
            
            # Add vectors to FAISS index
            logger.info(f"Adding {len(embeddings)} vectors to FAISS index...")
            self.faiss_index.add_vectors(embeddings, items)
            
            # Save the index
            if self.index_path:
                self._save_index()
            
            logger.info(f"Successfully built index with {len(items)} items from database")
            
        except Exception as e:
            logger.error(f"Error building index from database: {e}")
            raise
    
    def search(
        self, 
        query: str, 
        k: int = 10,
        filter_types: Optional[List[str]] = None,
        filter_categories: Optional[List[str]] = None,
        filter_providers: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar catalog items.
        
        Args:
            query: Search query text
            k: Number of results to return
            filter_types: Filter by tool types (e.g., ['action', 'trigger'])
            filter_categories: Filter by categories
            filter_providers: Filter by provider names
            
        Returns:
            List of search results with metadata and similarity scores
        """
        if not query or not query.strip():
            return []
        
        # Generate embedding for query
        query_embedding = self.embedding_service.embed_text(query)
        
        # Search in FAISS index
        distances, indices, metadata = self.faiss_index.search(query_embedding, k * 2)  # Get more results for filtering
        
        # Apply filters
        filtered_results = self._apply_filters(metadata, filter_types, filter_categories, filter_providers)
        
        # Limit results and add similarity scores
        results = []
        for i, item in enumerate(filtered_results[:k]):
            # Convert distance to similarity score (for cosine similarity, higher distance = higher similarity)
            similarity_score = float(distances[i]) if i < len(distances) else 0.0
            
            result = {
                "item": item,
                "similarity_score": similarity_score,
                "rank": i + 1
            }
            results.append(result)
        
        logger.info(f"Search for '{query}' returned {len(results)} results")
        return results
    
    def search_similar_tools(
        self, 
        tool_item: Dict[str, Any], 
        k: int = 5,
        exclude_self: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find tools similar to a given tool.
        
        Args:
            tool_item: Tool item to find similar tools for
            k: Number of similar tools to return
            exclude_self: Whether to exclude the input tool from results
            
        Returns:
            List of similar tools with similarity scores
        """
        # Generate embedding for the tool
        tool_embedding = self.embedding_service.embed_catalog_item(tool_item)
        
        # Search for similar items
        distances, indices, metadata = self.faiss_index.search(tool_embedding, k + 1)
        
        results = []
        for i, (distance, item) in enumerate(zip(distances, metadata)):
            # Skip the tool itself if exclude_self is True
            if exclude_self and self._is_same_tool(tool_item, item):
                continue
            
            similarity_score = float(distance)
            result = {
                "item": item,
                "similarity_score": similarity_score,
                "rank": len(results) + 1
            }
            results.append(result)
            
            if len(results) >= k:
                break
        
        return results
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the current index."""
        return {
            "faiss_stats": self.faiss_index.get_stats(),
            "embedding_model": self.embedding_service.get_model_info(),
            "index_path": str(self.index_path) if self.index_path else None
        }
    
    def rebuild_index(self, catalog_data: Dict[str, Any]) -> None:
        """Rebuild the entire index from scratch."""
        logger.info("Rebuilding FAISS index")
        self.faiss_index.clear()
        self.build_index_from_catalog(catalog_data)
    
    def _extract_catalog_items(self, catalog_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all catalog items for indexing."""
        items = []
        
        # Handle different catalog structures
        # Check if we have catalog.providers structure
        if "catalog" in catalog_data and "providers" in catalog_data["catalog"]:
            providers_data = catalog_data["catalog"]["providers"]
            categories_data = catalog_data["catalog"].get("categories", {})
        else:
            # Direct providers structure
            providers_data = catalog_data.get("providers", {})
            categories_data = catalog_data.get("categories", {})
        
        # Extract categories
        if categories_data:
            if isinstance(categories_data, dict):
                # Categories as dictionary
                for category_id, category in categories_data.items():
                    if isinstance(category, dict):
                        items.append({
                            "type": "category",
                            "id": category.get("slug", category_id),
                            "name": category.get("name", ""),
                            "description": category.get("description", ""),
                            "metadata": category
                        })
            elif isinstance(categories_data, list):
                # Categories as list
                for category in categories_data:
                    if isinstance(category, dict):
                        items.append({
                            "type": "category",
                            "id": category.get("slug", ""),
                            "name": category.get("name", ""),
                            "description": category.get("description", ""),
                            "metadata": category
                        })
        
        # Extract providers and their tools
        if providers_data:
            if isinstance(providers_data, dict):
                # Providers as dictionary (provider_id -> provider_data)
                for provider_id, provider in providers_data.items():
                    if not isinstance(provider, dict):
                        continue
                    
                    # Use the key as ID if not present in provider data
                    if "id" not in provider:
                        provider["id"] = provider_id
                    
                    self._extract_provider_items(provider, items)
            elif isinstance(providers_data, list):
                # Providers as list
                for provider in providers_data:
                    if isinstance(provider, dict):
                        self._extract_provider_items(provider, items)
        
        logger.info(f"Extracted {len(items)} catalog items")
        return items
    
    def _extract_database_catalog_items(self, providers_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all catalog items from database provider data."""
        items = []
        
        if not providers_data:
            return items
        
        for provider_slug, provider in providers_data.items():
            if not isinstance(provider, dict):
                continue
            
            # Add provider as an item
            items.append({
                "type": "provider",
                "id": provider.get("id", provider_slug),
                "slug": provider_slug,
                "name": provider.get("name", ""),
                "description": provider.get("description", ""),
                "category": provider.get("category", ""),
                "website": provider.get("website", ""),
                "version": provider.get("version", ""),
                "tool_count": provider.get("tool_count", 0),
                "action_count": provider.get("action_count", 0),
                "trigger_count": provider.get("trigger_count", 0),
                "metadata": provider,
                "provider_id": provider_slug
            })
            
            # Add all tools (actions and triggers)
            tools = provider.get("tools", [])
            for tool in tools:
                if not isinstance(tool, dict):
                    continue
                
                tool_type = tool.get("tool_type", "action")
                items.append({
                    "type": tool_type,
                    "id": f"{provider_slug}.{tool.get('slug', '')}",
                    "slug": tool.get("slug", ""),
                    "name": tool.get("name", ""),
                    "display_name": tool.get("display_name", tool.get("name", "")),
                    "description": tool.get("description", ""),
                    "tool_type": tool_type,
                    "version": tool.get("version", ""),
                    "input_schema": tool.get("input_schema", {}),
                    "output_schema": tool.get("output_schema", {}),
                    "tags": tool.get("tags", []),
                    "metadata": tool,
                    "provider_id": provider_slug,
                    "provider_name": provider.get("name", "")
                })
        
        logger.info(f"Extracted {len(items)} catalog items from database")
        return items
    
    def _extract_provider_items(self, provider: Dict[str, Any], items: List[Dict[str, Any]]) -> None:
        """Extract items from a single provider."""
        provider_id = provider.get("id", provider.get("slug", ""))
        
        # Add provider as an item
        items.append({
            "type": "provider",
            "id": provider_id,
            "name": provider.get("name", ""),
            "description": provider.get("description", ""),
            "category": provider.get("category", ""),
            "website": provider.get("website", ""),
            "metadata": provider,
            "provider_id": provider_id
        })
        
        # For the current catalog structure, tools are embedded within the provider stats
        # Additional tools/actions would be extracted here if available in the data structure
    
    def _apply_filters(
        self, 
        metadata: List[Dict[str, Any]], 
        filter_types: Optional[List[str]] = None,
        filter_categories: Optional[List[str]] = None,
        filter_providers: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Apply filters to search results."""
        filtered = metadata
        
        if filter_types:
            filtered = [item for item in filtered if item.get("type") in filter_types]
        
        if filter_categories:
            filtered = [item for item in filtered 
                       if item.get("metadata", {}).get("category") in filter_categories]
        
        if filter_providers:
            filtered = [item for item in filtered 
                       if item.get("provider_id") in filter_providers]
        
        return filtered
    
    def _is_same_tool(self, tool1: Dict[str, Any], tool2: Dict[str, Any]) -> bool:
        """Check if two tools are the same."""
        return (tool1.get("id") == tool2.get("id") or 
                (tool1.get("name") == tool2.get("name") and 
                 tool1.get("provider_id") == tool2.get("provider_id")))
    
    def _save_index(self) -> None:
        """Save the FAISS index to disk."""
        if self.index_path:
            self.faiss_index.save(self.index_path)
    
    def _load_index(self) -> None:
        """Load the FAISS index from disk."""
        if self.index_path and Path(f"{self.index_path}.faiss").exists():
            try:
                self.faiss_index.load(self.index_path)
                logger.info(f"Loaded existing index with {self.faiss_index.get_vector_count()} vectors")
            except Exception as e:
                logger.error(f"Failed to load index: {e}")
                logger.info("Will build new index from catalog data")
