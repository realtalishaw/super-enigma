import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from bson import ObjectId

from .models import Provider, ProviderMetadata, ActionSpec, TriggerSpec, ParamSpec, ParamType
from .cache import RedisCacheStore
from core.config import settings

logger = logging.getLogger(__name__)

class DatabaseCatalogService:
    """
    MongoDB-first catalog service that uses your existing database schema.
    Redis is used as a performance cache layer, not for data storage.
    """
    
    def __init__(self, database_url: str, redis_cache: RedisCacheStore):
        self.database_url = database_url
        self.redis_cache = redis_cache
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self.cache_ttl = 3600  # 1 hour cache TTL
        self.stale_threshold = timedelta(hours=24)  # 24 hours stale threshold
        
    async def _ensure_client(self):
        """Ensure MongoDB client is initialized"""
        if self.client is None:
            self.client = AsyncIOMotorClient(self.database_url)
            self.database = self.client.get_database()
            
            # Try to create indexes for better performance (optional)
            try:
                await self._create_indexes()
            except Exception as e:
                logger.warning(f"Index creation failed (continuing without indexes): {e}")
    
    async def _create_indexes(self):
        """Create MongoDB indexes for better performance"""
        try:
            # Check if indexes already exist before creating them
            existing_indexes = await self.database.toolkits.list_indexes().to_list(length=None)
            index_names = [idx['name'] for idx in existing_indexes]
            
            # Only create indexes if they don't already exist
            if "slug_1" not in index_names:
                await self.database.toolkits.create_index([("slug", ASCENDING)], unique=True)
            if "category_1" not in index_names:
                await self.database.toolkits.create_index([("category", ASCENDING)])
            if "last_synced_at_1" not in index_names:
                await self.database.toolkits.create_index([("last_synced_at", ASCENDING)])
            if "is_deprecated_1" not in index_names:
                await self.database.toolkits.create_index([("is_deprecated", ASCENDING)])
            
            # Check tools collection indexes
            existing_tools_indexes = await self.database.tools.list_indexes().to_list(length=None)
            tools_index_names = [idx['name'] for idx in existing_tools_indexes]
            
            if "toolkit_id_1" not in tools_index_names:
                await self.database.tools.create_index([("toolkit_id", ASCENDING)])
            if "slug_1" not in tools_index_names:
                await self.database.tools.create_index([("slug", ASCENDING)])
            if "tool_type_1" not in tools_index_names:
                await self.database.tools.create_index([("tool_type", ASCENDING)])
            if "is_deprecated_1" not in tools_index_names:
                await self.database.tools.create_index([("is_deprecated", ASCENDING)])
            
            # Check categories collection indexes
            existing_cat_indexes = await self.database.toolkit_categories.list_indexes().to_list(length=None)
            cat_index_names = [idx['name'] for idx in existing_cat_indexes]
            
            if "name_1" not in cat_index_names:
                await self.database.toolkit_categories.create_index([("name", ASCENDING)], unique=True)
            if "sort_order_1" not in cat_index_names:
                await self.database.toolkit_categories.create_index([("sort_order", ASCENDING)])
            
            logger.info("MongoDB indexes checked/created successfully")
        except Exception as e:
            logger.warning(f"Failed to create some indexes (this is usually fine if they already exist): {e}")
    
    async def get_catalog(
        self,
        providers: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        has_actions: Optional[bool] = None,
        has_triggers: Optional[bool] = None,
        force_refresh: bool = False,
        use_mcp: bool = False,
        use_sdk: bool = False
    ) -> Dict[str, Any]:
        """
        Get catalog data from MongoDB with Redis caching.
        
        Args:
            force_refresh: Force refresh from MCP/SDK and update database
            use_mcp: Explicitly use MCP fetcher (bypasses cache and database)
            use_sdk: Explicitly use SDK fetcher (bypasses cache and database)
        """
        # If explicitly requesting MCP/SDK, bypass everything
        if use_mcp or use_sdk:
            logger.info(f"Bypassing database and cache - using {'MCP' if use_mcp else 'SDK'} fetcher")
            return await self._fetch_from_external_sources(providers, categories, tags, has_actions, has_triggers, use_mcp, use_sdk)
        
        # Check Redis cache first for performance
        cache_key = self._generate_cache_key(providers, categories, tags, has_actions, has_triggers)
        cached_data = await self.redis_cache.get(cache_key)
        
        if cached_data and not force_refresh:
            logger.info("Returning data from Redis cache")
            return {
                "providers": cached_data,
                "source": "redis_cache",
                "cached_at": datetime.now(timezone.utc)
            }
        
        # Get data from MongoDB (primary source)
        logger.info("Fetching data from MongoDB")
        db_providers = await self._get_providers_from_database(
            providers, categories, tags, has_actions, has_triggers
        )
        
        # Check if any tools are stale and need refresh from MCP/SDK
        stale_toolkits = await self._get_stale_toolkits()
        
        if stale_toolkits and (force_refresh or len(stale_toolkits) > 0):
            logger.info(f"Found {len(stale_toolkits)} stale toolkits, refreshing from external sources")
            await self._refresh_stale_toolkits(stale_toolkits)
            
            # Fetch updated data from database
            db_providers = await self._get_providers_from_database(
                providers, categories, tags, has_actions, has_triggers
            )
        
        # Cache the result in Redis for performance
        if db_providers:
            await self.redis_cache.set(cache_key, db_providers, self.cache_ttl)
        
        return {
            "providers": db_providers,
            "source": "mongodb",
            "cached_at": datetime.now(timezone.utc),
            "stale_toolkits_count": len(stale_toolkits) if stale_toolkits else 0
        }
    
    async def get_provider(
        self,
        provider_id: str,
        force_refresh: bool = False,
        use_mcp: bool = False,
        use_sdk: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get specific provider from MongoDB with caching"""
        # If explicitly requesting MCP/SDK, bypass everything
        if use_mcp or use_sdk:
            return await self._fetch_provider_from_external(provider_id, use_mcp, use_sdk)
        
        # Check Redis cache first
        cache_key = f"provider:{provider_id}"
        cached_provider = await self.redis_cache.get(cache_key)
        
        if cached_provider and not force_refresh:
            return cached_provider
        
        # Get from MongoDB
        provider = await self._get_provider_from_database(provider_id)
        
        if provider:
            # Cache the result
            await self.redis_cache.set(cache_key, provider, self.cache_ttl)
        
        return provider
    
    async def search_providers(
        self,
        query: str,
        limit: int = 50,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """Search providers in MongoDB"""
        if not query.strip():
            return []
        
        # Check cache first
        cache_key = f"search:{query}:{limit}"
        cached_results = await self.redis_cache.get(cache_key)
        
        if cached_results and not force_refresh:
            return cached_results
        
        # Search in MongoDB
        results = await self._search_providers_in_database(query, limit)
        
        # Cache results
        if results:
            await self.redis_cache.set(cache_key, results, self.cache_ttl)
        
        return results
    
    async def get_categories(self) -> List[str]:
        """Get categories from MongoDB"""
        await self._ensure_client()
        
        try:
            cursor = self.database.toolkit_categories.find(
                {}, 
                {"name": 1, "sort_order": 1}
            ).sort([("sort_order", ASCENDING), ("name", ASCENDING)])
            
            categories = []
            async for doc in cursor:
                categories.append(doc["name"])
            
            return categories
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []
    
    async def get_tags(self) -> List[str]:
        """Get tags from MongoDB (could be extracted from descriptions or other fields)"""
        # For now, return empty list since tags aren't explicitly stored
        # Could be enhanced to extract tags from descriptions or add a tags collection
        return []
    
    async def health_check(self) -> bool:
        """Check MongoDB and Redis health"""
        try:
            # Check Redis
            redis_healthy = await self.redis_cache.health_check()
            
            # Check MongoDB
            await self._ensure_client()
            await self.client.admin.command('ping')
            db_healthy = True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            db_healthy = False
        
        return redis_healthy and db_healthy
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get MongoDB statistics"""
        await self._ensure_client()
        
        try:
            # Get toolkit count
            toolkit_count = await self.database.toolkits.count_documents({"is_deprecated": False})
            
            # Get tool count
            tool_count = await self.database.tools.count_documents({"is_deprecated": False})
            
            # Get stale toolkit count
            stale_threshold = datetime.now(timezone.utc) - self.stale_threshold
            stale_count = await self.database.toolkits.count_documents({
                "last_synced_at": {"$lt": stale_threshold},
                "is_deprecated": False
            })
            
            # Get last sync info
            last_sync_doc = await self.database.toolkits.find_one(
                {"is_deprecated": False},
                sort=[("last_synced_at", DESCENDING)]
            )
            last_sync = last_sync_doc.get("last_synced_at") if last_sync_doc else None
            
            return {
                "toolkit_count": toolkit_count,
                "tool_count": tool_count,
                "stale_toolkit_count": stale_count,
                "last_sync": last_sync.isoformat() if last_sync else None,
                "stale_threshold_hours": 24
            }
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {"error": str(e)}
    
    async def _get_providers_from_database(
        self,
        providers: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        has_actions: Optional[bool] = None,
        has_triggers: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """Get providers from MongoDB with filtering"""
        await self._ensure_client()
        
        try:
            # Build filter
            filter_query = {"is_deprecated": False}
            
            if providers:
                filter_query["slug"] = {"$in": providers}
            
            if categories:
                filter_query["category"] = {"$in": categories}
            
            # Get toolkits
            cursor = self.database.toolkits.find(filter_query)
            toolkit_docs = await cursor.to_list(length=None)
            
            providers_data = []
            for toolkit_doc in toolkit_docs:
                # Get tools for this toolkit
                tools = await self._get_tools_for_provider(str(toolkit_doc["_id"]))
                
                # Count tools by type
                action_count = len([t for t in tools if t.get("tool_type") == "action"])
                trigger_count = len([t for t in tools if t.get("tool_type") == "trigger"])
                
                provider = {
                    "id": str(toolkit_doc["_id"]),
                    "slug": toolkit_doc["slug"],
                    "name": toolkit_doc["name"],
                    "description": toolkit_doc.get("description", ""),
                    "website": toolkit_doc.get("website_url", ""),
                    "category": toolkit_doc.get("category", ""),
                    "version": toolkit_doc.get("version", "1.0.0"),
                    "created_at": toolkit_doc.get("created_at"),
                    "updated_at": toolkit_doc.get("updated_at"),
                    "last_synced_at": toolkit_doc.get("last_synced_at"),
                    "tool_count": len(tools),
                    "action_count": action_count,
                    "trigger_count": trigger_count,
                    "has_actions": action_count > 0,
                    "has_triggers": trigger_count > 0,
                    "tools": tools,
                    "triggers": [t for t in tools if t.get("tool_type") == "trigger"],
                    "actions": [t for t in tools if t.get("tool_type") == "action"]
                }
                
                # Apply additional filters
                if has_actions is not None and provider["has_actions"] != has_actions:
                    continue
                if has_triggers is not None and provider["has_triggers"] != has_triggers:
                    continue
                
                providers_data.append(provider)
            
            # Convert list to dictionary with slug as key
            providers_dict = {}
            for provider in providers_data:
                providers_dict[provider["slug"]] = provider
            
            return providers_dict
                
        except Exception as e:
            logger.error(f"Error getting providers from database: {e}")
            return []
    
    async def _get_tools_for_provider(self, provider_id: str) -> List[Dict[str, Any]]:
        """Get tools for a specific provider"""
        await self._ensure_client()
        
        try:
            cursor = self.database.tools.find({
                "toolkit_id": provider_id,
                "is_deprecated": False
            }).sort("name", ASCENDING)
            
            tools = []
            async for doc in cursor:
                tool = {
                    "id": str(doc["_id"]),
                    "slug": doc["slug"],
                    "name": doc["name"],
                    "display_name": doc.get("display_name", doc["name"]),
                    "description": doc.get("description", ""),
                    "tool_type": doc["tool_type"],
                    "version": doc.get("version", "1.0.0"),
                    "input_schema": doc.get("input_schema", {}),
                    "output_schema": doc.get("output_schema", {}),
                    "tags": doc.get("tags", [])
                }
                tools.append(tool)
            
            return tools
                
        except Exception as e:
            logger.error(f"Error getting tools for provider {provider_id}: {e}")
            return []
    
    async def _get_provider_from_database(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get specific provider from MongoDB"""
        await self._ensure_client()
        
        try:
            # Get toolkit info
            toolkit_doc = await self.database.toolkits.find_one({
                "_id": ObjectId(provider_id) if ObjectId.is_valid(provider_id) else provider_id,
                "is_deprecated": False
            })
            
            if not toolkit_doc:
                return None
            
            # Get tools for this toolkit
            tools = await self._get_tools_for_provider(str(toolkit_doc["_id"]))
            
            # Convert to provider format
            provider = {
                "id": str(toolkit_doc["_id"]),
                "name": toolkit_doc["name"],
                "description": toolkit_doc.get("description", ""),
                "website": toolkit_doc.get("website_url", ""),
                "category": toolkit_doc.get("category", ""),
                "version": toolkit_doc.get("version", "1.0.0"),
                "created_at": toolkit_doc.get("created_at"),
                "updated_at": toolkit_doc.get("updated_at"),
                "last_synced_at": toolkit_doc.get("last_synced_at"),
                "tools": tools
            }
            
            return provider
                
        except Exception as e:
            logger.error(f"Error getting provider {provider_id} from database: {e}")
            return None
    
    async def _search_providers_in_database(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search providers in MongoDB"""
        await self._ensure_client()
        
        try:
            # Create text search query
            search_filter = {
                "is_deprecated": False,
                "$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                    {"category": {"$regex": query, "$options": "i"}}
                ]
            }
            
            cursor = self.database.toolkits.find(search_filter).limit(limit)
            results = []
            
            async for doc in cursor:
                results.append({
                    "id": str(doc["_id"]),
                    "name": doc["name"],
                    "description": doc.get("description", ""),
                    "category": doc.get("category", "")
                })
            
            return results
                
        except Exception as e:
            logger.error(f"Error searching providers in database: {e}")
            return []
    
    async def _get_stale_toolkits(self) -> List[str]:
        """Get list of toolkits that are stale and need refresh"""
        await self._ensure_client()
        
        try:
            stale_threshold = datetime.now(timezone.utc) - self.stale_threshold
            
            cursor = self.database.toolkits.find({
                "last_synced_at": {"$lt": stale_threshold},
                "is_deprecated": False
            }).sort("last_synced_at", ASCENDING)
            
            stale_toolkits = []
            async for doc in cursor:
                stale_toolkits.append(str(doc["_id"]))
            
            return stale_toolkits
                
        except Exception as e:
            logger.error(f"Error getting stale toolkits: {e}")
            return []
    
    async def _refresh_stale_toolkits(self, toolkit_ids: List[str]) -> bool:
        """Refresh stale toolkits from external sources (MCP/SDK)"""
        # This would integrate with your existing MCP/SDK fetchers
        # For now, just update the last_synced_at timestamp
        logger.info(f"Refreshing {len(toolkit_ids)} stale toolkits from external sources")
        
        await self._ensure_client()
        
        try:
            # Convert string IDs to ObjectIds
            object_ids = [ObjectId(tid) for tid in toolkit_ids if ObjectId.is_valid(tid)]
            
            if object_ids:
                result = await self.database.toolkits.update_many(
                    {"_id": {"$in": object_ids}},
                    {"$set": {"last_synced_at": datetime.now(timezone.utc)}}
                )
                
                logger.info(f"Successfully updated last_synced_at for {result.modified_count} toolkits")
                return True
            else:
                logger.warning("No valid ObjectIds found for stale toolkits")
                return False
                
        except Exception as e:
            logger.error(f"Error refreshing stale toolkits: {e}")
            return False
    
    async def _fetch_from_external_sources(
        self,
        providers: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        has_actions: Optional[bool] = None,
        has_triggers: Optional[bool] = None,
        use_mcp: bool = True,
        use_sdk: bool = True
    ) -> Dict[str, Any]:
        """Fetch data from external sources (MCP/SDK) - placeholder implementation"""
        # This would integrate with your existing MCP/SDK fetchers
        logger.info("Fetching from external sources (MCP/SDK)")
        
        return {
            "providers": [],
            "source": "external_fetchers",
            "cached_at": datetime.now(timezone.utc)
        }
    
    async def _fetch_provider_from_external(
        self,
        provider_id: str,
        use_mcp: bool = True,
        use_sdk: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Fetch specific provider from external sources - placeholder implementation"""
        # This would integrate with your existing MCP/SDK fetchers
        logger.info(f"Fetching provider {provider_id} from external sources")
        return None
    
    def _generate_cache_key(
        self,
        providers: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        has_actions: Optional[bool] = None,
        has_triggers: Optional[bool] = None
    ) -> str:
        """Generate cache key for Redis"""
        parts = ["catalog"]
        
        if providers:
            parts.extend(["providers"] + sorted(providers))
        if categories:
            parts.extend(["categories"] + sorted(categories))
        if tags:
            parts.extend(["tags"] + sorted(tags))
        if has_actions is not None:
            parts.append(f"actions_{has_actions}")
        if has_triggers is not None:
            parts.append(f"triggers_{has_triggers}")
        
        return ":".join(parts)

    async def get_provider_by_slug(self, provider_slug: str, force_refresh: bool = False, use_mcp: bool = False, use_sdk: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get a specific provider by slug.
        
        Args:
            provider_slug: The slug identifier for the provider
            force_refresh: Force refresh from external sources
            use_mcp: Use MCP fetcher
            use_sdk: Use SDK fetcher
        """
        # If explicitly requesting MCP/SDK, bypass everything
        if use_mcp or use_sdk:
            logger.info(f"Bypassing database and cache - using {'MCP' if use_mcp else 'SDK'} fetcher")
            # This would need to be implemented based on your external fetchers
            return None
        
        # Check Redis cache first for performance
        cache_key = f"provider_slug:{provider_slug}"
        cached_data = await self.redis_cache.get(cache_key)
        
        if cached_data and not force_refresh:
            logger.info(f"Returning provider '{provider_slug}' from Redis cache")
            return cached_data
        
        # Get data from database (primary source)
        logger.info(f"Fetching provider '{provider_slug}' from database")
        provider = await self._get_provider_from_database_by_slug(provider_slug)
        
        if provider:
            # Cache the result in Redis for performance
            await self.redis_cache.set(cache_key, provider, self.cache_ttl)
        
        return provider

    async def _get_provider_from_database_by_slug(self, provider_slug: str) -> Optional[Dict[str, Any]]:
        """Get specific provider from MongoDB by slug"""
        await self._ensure_client()
        
        try:
            # Get toolkit info by slug
            toolkit_doc = await self.database.toolkits.find_one({
                "slug": provider_slug,
                "is_deprecated": False
            })
            
            if not toolkit_doc:
                return None
            
            # Get tools for this toolkit
            tools = await self._get_tools_for_provider(str(toolkit_doc["_id"]))
            
            # Convert to provider format
            provider = {
                "id": str(toolkit_doc["_id"]),
                "slug": toolkit_doc["slug"],
                "name": toolkit_doc["name"],
                "description": toolkit_doc.get("description", ""),
                "website": toolkit_doc.get("website_url", ""),
                "category": toolkit_doc.get("category", ""),
                "version": toolkit_doc.get("version", "1.0.0"),
                "created_at": toolkit_doc.get("created_at"),
                "updated_at": toolkit_doc.get("updated_at"),
                "last_synced_at": toolkit_doc.get("last_synced_at"),
                "tools": tools
            }
            
            return provider
                
        except Exception as e:
            logger.error(f"Error getting provider with slug '{provider_slug}' from database: {e}")
            return None

    async def get_tool_by_slug(self, tool_slug: str, provider_slug: Optional[str] = None, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get a specific tool by slug, optionally filtered by provider.
        
        Args:
            tool_slug: The slug of the tool (e.g., 'GMAIL_CREATE_EMAIL_DRAFT')
            provider_slug: Optional provider slug to filter by
            force_refresh: Force refresh from external sources
        """
        await self._ensure_client()
        
        try:
            # Build the filter based on whether we're filtering by provider
            if provider_slug:
                # Get toolkit ID first
                toolkit_doc = await self.database.toolkits.find_one({
                    "slug": provider_slug,
                    "is_deprecated": False
                })
                
                if not toolkit_doc:
                    return None
                
                # Get tool from specific provider
                tool_doc = await self.database.tools.find_one({
                    "slug": tool_slug,
                    "toolkit_id": str(toolkit_doc["_id"]),
                    "is_deprecated": False
                })
                
                if not tool_doc:
                    return None
                
                # Parse the input schema to extract parameters
                parameters = self._parse_input_schema(tool_doc.get("input_schema", {}))
                
                tool_data = {
                    "tool": {
                        "slug": tool_doc["slug"],
                        "name": tool_doc["name"],
                        "display_name": tool_doc.get("display_name", tool_doc["name"]),
                        "description": tool_doc.get("description", ""),
                        "tool_type": tool_doc["tool_type"],
                        "version": tool_doc.get("version", "1.0.0"),
                        "parameters": parameters,
                        "input_schema": tool_doc.get("input_schema", {}),
                        "output_schema": tool_doc.get("output_schema", {}),
                        "tags": tool_doc.get("tags", [])
                    },
                    "provider": {
                        "slug": provider_slug,
                        "name": toolkit_doc["name"]
                    }
                }
                
                return tool_data
            else:
                # Get tool from any provider
                cursor = self.database.tools.find({
                    "slug": tool_slug,
                    "is_deprecated": False
                })
                
                tools_by_provider = {}
                
                async for tool_doc in cursor:
                    # Get toolkit info
                    toolkit_doc = await self.database.toolkits.find_one({
                        "_id": ObjectId(tool_doc["toolkit_id"]),
                        "is_deprecated": False
                    })
                    
                    if toolkit_doc:
                        provider_slug = toolkit_doc["slug"]
                        
                        # Parse the input schema to extract parameters
                        parameters = self._parse_input_schema(tool_doc.get("input_schema", {}))
                        
                        tools_by_provider[provider_slug] = {
                            "tool": {
                                "slug": tool_doc["slug"],
                                "name": tool_doc["name"],
                                "display_name": tool_doc.get("display_name", tool_doc["name"]),
                                "description": tool_doc.get("description", ""),
                                "tool_type": tool_doc["tool_type"],
                                "version": tool_doc.get("version", "1.0.0"),
                                "parameters": parameters,
                                "input_schema": tool_doc.get("input_schema", {}),
                                "output_schema": tool_doc.get("output_schema", {}),
                                "tags": tool_doc.get("tags", [])
                            },
                            "provider": {
                                "slug": provider_slug,
                                "name": toolkit_doc["name"]
                            }
                        }
                
                # Return all providers that have this tool
                return {
                    "tool_slug": tool_slug,
                    "providers": list(tools_by_provider.values())
                }
                
        except Exception as e:
            logger.error(f"Error getting tool by slug '{tool_slug}' from database: {e}")
            return None

    async def get_tool(self, tool_name: str, provider_slug: Optional[str] = None, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get a specific tool by name, optionally filtered by provider.
        
        Args:
            tool_name: The name of the tool (e.g., 'chat.postMessage')
            provider_slug: Optional provider slug to filter by
            force_refresh: Force refresh from external sources
        """
        await self._ensure_client()
        
        try:
            # Build the filter based on whether we're filtering by provider
            if provider_slug:
                # Get toolkit ID first
                toolkit_doc = await self.database.toolkits.find_one({
                    "slug": provider_slug,
                    "is_deprecated": False
                })
                
                if not toolkit_doc:
                    return None
                
                # Get tool from specific provider
                tool_doc = await self.database.tools.find_one({
                    "name": tool_name,
                    "toolkit_id": str(toolkit_doc["_id"]),
                    "is_deprecated": False
                })
                
                if not tool_doc:
                    return None
                
                # Parse the input schema to extract parameters
                parameters = self._parse_input_schema(tool_doc.get("input_schema", {}))
                
                tool_data = {
                    "tool": {
                        "slug": tool_doc["slug"],
                        "name": tool_doc["name"],
                        "display_name": tool_doc.get("display_name", tool_doc["name"]),
                        "description": tool_doc.get("description", ""),
                        "tool_type": tool_doc["tool_type"],
                        "version": tool_doc.get("version", "1.0.0"),
                        "parameters": parameters,
                        "input_schema": tool_doc.get("input_schema", {}),
                        "output_schema": tool_doc.get("output_schema", {}),
                        "tags": tool_doc.get("tags", [])
                    },
                    "provider": {
                        "slug": provider_slug,
                        "name": toolkit_doc["name"]
                    }
                }
                
                return tool_data
            else:
                # Get tool from any provider
                cursor = self.database.tools.find({
                    "name": tool_name,
                    "is_deprecated": False
                })
                
                tools_by_provider = {}
                
                async for tool_doc in cursor:
                    # Get toolkit info
                    toolkit_doc = await self.database.toolkits.find_one({
                        "_id": ObjectId(tool_doc["toolkit_id"]),
                        "is_deprecated": False
                    })
                    
                    if toolkit_doc:
                        provider_slug = toolkit_doc["slug"]
                        
                        # Parse the input schema to extract parameters
                        parameters = self._parse_input_schema(tool_doc.get("input_schema", {}))
                        
                        tools_by_provider[provider_slug] = {
                            "tool": {
                                "slug": tool_doc["slug"],
                                "name": tool_doc["name"],
                                "display_name": tool_doc.get("display_name", tool_doc["name"]),
                                "description": tool_doc.get("description", ""),
                                "tool_type": tool_doc["tool_type"],
                                "version": tool_doc.get("version", "1.0.0"),
                                "parameters": parameters,
                                "input_schema": tool_doc.get("input_schema", {}),
                                "output_schema": tool_doc.get("output_schema", {}),
                                "tags": tool_doc.get("tags", [])
                            },
                            "provider": {
                                "slug": provider_slug,
                                "name": toolkit_doc["name"]
                            }
                        }
                
                # Return all providers that have this tool
                return {
                    "tool_name": tool_name,
                    "providers": list(tools_by_provider.values())
                }
                
        except Exception as e:
            logger.error(f"Error getting tool '{tool_name}' from database: {e}")
            return None

    async def search_tools(self, query: Optional[str] = None, provider_slug: Optional[str] = None, tool_type: Optional[str] = None, limit: int = 50, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Search for tools across all providers or within a specific provider.
        
        Args:
            query: Optional search query for tool names
            provider_slug: Optional provider slug to filter by
            tool_type: Optional tool type filter (action, trigger, both)
            limit: Maximum number of results
            force_refresh: Force refresh from external sources
        """
        await self._ensure_client()
        
        try:
            # Build the base filter
            base_filter = {"is_deprecated": False}
            
            # Add provider filter if specified
            if provider_slug:
                toolkit_doc = await self.database.toolkits.find_one({
                    "slug": provider_slug,
                    "is_deprecated": False
                })
                
                if not toolkit_doc:
                    return {
                        "query": query,
                        "provider_filter": provider_slug,
                        "tool_type_filter": tool_type,
                        "total_tools": 0,
                        "total_providers": 0,
                        "results": [],
                        "error": "Provider not found"
                    }
                
                base_filter["toolkit_id"] = str(toolkit_doc["_id"])
            
            # Add tool type filter if specified
            if tool_type:
                base_filter["tool_type"] = tool_type
            
            # Add search query if specified
            if query:
                base_filter["$or"] = [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"display_name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}}
                ]
            
            # Execute query
            cursor = self.database.tools.find(base_filter).limit(limit)
            tool_docs = await cursor.to_list(length=None)
            
            # Group tools by provider
            tools_by_provider = {}
            
            for tool_doc in tool_docs:
                # Get toolkit info
                toolkit_doc = await self.database.toolkits.find_one({
                    "_id": ObjectId(tool_doc["toolkit_id"]),
                    "is_deprecated": False
                })
                
                if toolkit_doc:
                    provider_slug = toolkit_doc["slug"]
                    
                    if provider_slug not in tools_by_provider:
                        tools_by_provider[provider_slug] = {
                            "provider": {
                                "slug": provider_slug,
                                "name": toolkit_doc["name"]
                            },
                            "tools": []
                        }
                    
                    tool = {
                        "slug": tool_doc["slug"],
                        "name": tool_doc["name"],
                        "display_name": tool_doc.get("display_name", tool_doc["name"]),
                        "description": tool_doc.get("description", ""),
                        "tool_type": tool_doc["tool_type"],
                        "version": tool_doc.get("version", "1.0.0"),
                        "input_schema": tool_doc.get("input_schema", {}),
                        "output_schema": tool_doc.get("output_schema", {}),
                        "tags": tool_doc.get("tags", [])
                    }
                    tools_by_provider[provider_slug]["tools"].append(tool)
            
            return {
                "query": query,
                "provider_filter": provider_slug,
                "tool_type_filter": tool_type,
                "total_tools": sum(len(provider["tools"]) for provider in tools_by_provider.values()),
                "total_providers": len(tools_by_provider),
                "results": list(tools_by_provider.values())
            }
                
        except Exception as e:
            logger.error(f"Error searching tools in database: {e}")
            return {
                "query": query,
                "provider_filter": provider_slug,
                "tool_type_filter": tool_type,
                "total_tools": 0,
                "total_providers": 0,
                "results": [],
                "error": str(e)
            }

    def _parse_input_schema(self, input_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse input schema to extract parameters"""
        parameters = []
        
        if input_schema and isinstance(input_schema, dict):
            properties = input_schema.get('properties', {})
            required = input_schema.get('required', [])
            
            for param_name, param_spec in properties.items():
                if isinstance(param_spec, dict):
                    param = {
                        "name": param_name,
                        "display_name": param_spec.get('title', param_name),
                        "description": param_spec.get('description', ''),
                        "type": param_spec.get('type', 'string'),
                        "required": param_name in required,
                        "default": param_spec.get('default'),
                        "validation": {
                            "examples": param_spec.get('examples', []),
                            "nullable": param_spec.get('nullable', False)
                        }
                    }
                    parameters.append(param)
        
        return parameters
