import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select, and_, or_
from sqlalchemy.sql import func

from .models import Provider, ProviderMetadata, ActionSpec, TriggerSpec, ParamSpec, ParamType
from .cache import RedisCacheStore
from core.config import settings

logger = logging.getLogger(__name__)

class DatabaseCatalogService:
    """
    Database-first catalog service that uses your existing database schema.
    Redis is used as a performance cache layer, not for data storage.
    """
    
    def __init__(self, database_url: str, redis_cache: RedisCacheStore):
        self.database_url = database_url
        self.redis_cache = redis_cache
        self.engine = None
        self.session_factory = None
        self.cache_ttl = 3600  # 1 hour cache TTL
        self.stale_threshold = timedelta(hours=24)  # 24 hours stale threshold
        
    async def _ensure_engine(self):
        """Ensure database engine is initialized"""
        if self.engine is None:
            # Convert PostgreSQL URL to async version
            async_url = self.database_url.replace('postgresql://', 'postgresql+asyncpg://')
            self.engine = create_async_engine(async_url, echo=False)
            self.session_factory = sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )
    
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
        Get catalog data from database with Redis caching.
        
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
        
        # Get data from database (primary source)
        logger.info("Fetching data from database")
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
            "source": "database",
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
        """Get specific provider from database with caching"""
        # If explicitly requesting MCP/SDK, bypass everything
        if use_mcp or use_sdk:
            return await self._fetch_provider_from_external(provider_id, use_mcp, use_sdk)
        
        # Check Redis cache first
        cache_key = f"provider:{provider_id}"
        cached_provider = await self.redis_cache.get(cache_key)
        
        if cached_provider and not force_refresh:
            return cached_provider
        
        # Get from database
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
        """Search providers in database"""
        if not query.strip():
            return []
        
        # Check cache first
        cache_key = f"search:{query}:{limit}"
        cached_results = await self.redis_cache.get(cache_key)
        
        if cached_results and not force_refresh:
            return cached_results
        
        # Search in database
        results = await self._search_providers_in_database(query, limit)
        
        # Cache results
        if results:
            await self.redis_cache.set(cache_key, results, self.cache_ttl)
        
        return results
    
    async def get_categories(self) -> List[str]:
        """Get categories from database"""
        await self._ensure_engine()
        
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT name FROM toolkit_categories ORDER BY sort_order, name")
            )
            categories = [row[0] for row in result.fetchall()]
            return categories
    
    async def get_tags(self) -> List[str]:
        """Get tags from database (could be extracted from descriptions or other fields)"""
        # For now, return empty list since tags aren't explicitly stored
        # Could be enhanced to extract tags from descriptions or add a tags table
        return []
    
    async def health_check(self) -> bool:
        """Check database and Redis health"""
        try:
            # Check Redis
            redis_healthy = await self.redis_cache.health_check()
            
            # Check database
            await self._ensure_engine()
            async with self.session_factory() as session:
                await session.execute(text("SELECT 1"))
                db_healthy = True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            db_healthy = False
        
        return redis_healthy and db_healthy
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        await self._ensure_engine()
        
        try:
            async with self.session_factory() as session:
                # Get toolkit count
                toolkit_result = await session.execute(text("SELECT COUNT(*) FROM toolkits"))
                toolkit_count = toolkit_result.scalar()
                
                # Get tool count
                tool_result = await session.execute(text("SELECT COUNT(*) FROM tools"))
                tool_count = tool_result.scalar()
                
                # Get stale toolkit count
                stale_result = await session.execute(
                    text("SELECT COUNT(*) FROM toolkits WHERE last_synced_at < NOW() - INTERVAL '24 hours'")
                )
                stale_count = stale_result.scalar()
                
                # Get last sync info
                last_sync_result = await session.execute(
                    text("SELECT MAX(last_synced_at) FROM toolkits")
                )
                last_sync = last_sync_result.scalar()
                
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
        """Get providers from database with filtering"""
        await self._ensure_engine()
        
        try:
            async with self.session_factory() as session:
                # Build base query
                query = text("""
                    SELECT 
                        t.toolkit_id,
                        t.slug,
                        t.name,
                        t.description,
                        t.website_url,
                        t.category,
                        t.version,
                        t.created_at,
                        t.updated_at,
                        t.last_synced_at,
                        COUNT(DISTINCT tools.tool_id) as tool_count,
                        COUNT(DISTINCT CASE WHEN tools.tool_type = 'action' THEN tools.tool_id END) as action_count,
                        COUNT(DISTINCT CASE WHEN tools.tool_type = 'trigger' THEN tools.tool_id END) as trigger_count
                    FROM toolkits t
                    LEFT JOIN tools ON t.toolkit_id = tools.toolkit_id
                    WHERE t.is_deprecated = FALSE
                """)
                
                # Add filters
                params = {}
                conditions = []
                
                if providers:
                    placeholders = ','.join([f':provider_{i}' for i in range(len(providers))])
                    conditions.append(f"t.slug IN ({placeholders})")
                    for i, provider in enumerate(providers):
                        params[f'provider_{i}'] = provider
                
                if categories:
                    placeholders = ','.join([f':category_{i}' for i in range(len(categories))])
                    conditions.append(f"t.category IN ({placeholders})")
                    for i, category in enumerate(categories):
                        params[f'category_{i}'] = category
                
                if conditions:
                    query = text(str(query) + " AND " + " AND ".join(conditions))
                
                query = text(str(query) + " GROUP BY t.toolkit_id, t.slug, t.name, t.description, t.website_url, t.category, t.version, t.created_at, t.updated_at, t.last_synced_at ORDER BY t.name")
                
                result = await session.execute(query, params)
                rows = result.fetchall()
                
                providers_data = []
                for row in rows:
                    provider = {
                        "id": row.toolkit_id,
                        "slug": row.slug,
                        "name": row.name,
                        "description": row.description,
                        "website": row.website_url,
                        "category": row.category,
                        "version": row.version,
                        "created_at": row.created_at,
                        "updated_at": row.updated_at,
                        "last_synced_at": row.last_synced_at,
                        "tool_count": row.tool_count,
                        "action_count": row.action_count,
                        "trigger_count": row.trigger_count,
                        "has_actions": row.action_count > 0,
                        "has_triggers": row.trigger_count > 0
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
                    # Get the actual tools for this provider
                    tools = await self._get_tools_for_provider(provider["id"])
                    
                    # Add tools to provider data
                    provider["tools"] = tools
                    provider["triggers"] = [t for t in tools if t.get("tool_type") == "trigger"]
                    provider["actions"] = [t for t in tools if t.get("tool_type") == "action"]
                    
                    providers_dict[provider["slug"]] = provider
                
                return providers_dict
                
        except Exception as e:
            logger.error(f"Error getting providers from database: {e}")
            return []
    
    async def _get_tools_for_provider(self, provider_id: str) -> List[Dict[str, Any]]:
        """Get tools for a specific provider"""
        await self._ensure_engine()
        
        try:
            async with self.session_factory() as session:
                tools_query = text("""
                    SELECT 
                        tool_id, name, display_name, description, tool_type, version,
                        input_schema, output_schema, tags
                    FROM tools 
                    WHERE toolkit_id = :toolkit_id AND is_deprecated = FALSE
                    ORDER BY name
                """)
                
                result = await session.execute(tools_query, {"toolkit_id": provider_id})
                tools = []
                
                for row in result.fetchall():
                    tool = {
                        "id": row.tool_id,
                        "name": row.name,
                        "display_name": row.display_name,
                        "description": row.description,
                        "tool_type": row.tool_type,
                        "version": row.version,
                        "input_schema": row.input_schema,
                        "output_schema": row.output_schema,
                        "tags": row.tags
                    }
                    tools.append(tool)
                
                return tools
                
        except Exception as e:
            logger.error(f"Error getting tools for provider {provider_id}: {e}")
            return []
    
    async def _get_provider_from_database(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get specific provider from database"""
        await self._ensure_engine()
        
        try:
            async with self.session_factory() as session:
                # Get toolkit info
                toolkit_query = text("""
                    SELECT 
                        toolkit_id, name, description, website_url, category, 
                        version, created_at, updated_at, last_synced_at
                    FROM toolkits 
                    WHERE toolkit_id = :toolkit_id AND is_deprecated = FALSE
                """)
                
                toolkit_result = await session.execute(toolkit_query, {"toolkit_id": provider_id})
                toolkit_row = toolkit_result.fetchone()
                
                if not toolkit_row:
                    return None
                
                # Get tools for this toolkit
                tools_query = text("""
                    SELECT 
                        t.name, t.display_name, t.description, t.tool_type, t.version,
                        p.name as param_name, p.name as param_display, p.description as param_description,
                        p.param_type, p.is_required, p.default_value, p.validation_rules
                    FROM tools t
                    LEFT JOIN tool_parameters p ON t.tool_id = p.tool_id
                    WHERE t.toolkit_id = :toolkit_id AND t.is_deprecated = FALSE
                    ORDER BY t.name, p.sort_order
                """)
                
                tools_result = await session.execute(tools_query, {"toolkit_id": provider_id})
                tools_data = {}
                
                for row in tools_result.fetchall():
                    tool_name = row.name
                    if tool_name not in tools_data:
                        tools_data[tool_name] = {
                            "name": tool_name,
                            "display_name": row.display_name,
                            "description": row.description,
                            "tool_type": row.tool_type,
                            "version": row.version,
                            "parameters": []
                        }
                    
                    if row.param_name:  # Has parameters
                        param = {
                            "name": row.param_name,
                            "display_name": row.param_display,
                            "description": row.param_description,
                            "type": row.param_type,
                            "required": row.is_required,
                            "default": row.default_value,
                            "validation": row.validation_rules
                        }
                        tools_data[tool_name]["parameters"].append(param)
                
                # Convert to provider format
                provider = {
                    "id": toolkit_row.toolkit_id,
                    "name": toolkit_row.name,
                    "description": toolkit_row.description,
                    "website": toolkit_row.website_url,
                    "category": toolkit_row.category_id,
                    "version": toolkit_row.version,
                    "created_at": toolkit_row.created_at,
                    "updated_at": toolkit_row.updated_at,
                    "last_synced_at": toolkit_row.last_synced_at,
                    "tools": list(tools_data.values())
                }
                
                return provider
                
        except Exception as e:
            logger.error(f"Error getting provider {provider_id} from database: {e}")
            return None
    
    async def _search_providers_in_database(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search providers in database"""
        await self._ensure_engine()
        
        try:
            async with self.session_factory() as session:
                search_query = text("""
                    SELECT DISTINCT
                        t.toolkit_id, t.name, t.description, t.category
                    FROM toolkits t
                    LEFT JOIN tools tools ON t.toolkit_id = tools.toolkit_id
                    WHERE t.is_deprecated = FALSE
                    AND (
                        t.name ILIKE :query OR 
                        t.description ILIKE :query OR
                        t.category ILIKE :query OR
                        tools.name ILIKE :query OR
                        tools.description ILIKE :query
                    )
                    ORDER BY t.name
                    LIMIT :limit
                """)
                
                result = await session.execute(search_query, {
                    "query": f"%{query}%",
                    "limit": limit
                })
                
                rows = result.fetchall()
                return [
                    {
                        "id": row.toolkit_id,
                        "name": row.name,
                        "description": row.description,
                        "category": row.category
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"Error searching providers in database: {e}")
            return []
    
    async def _get_stale_toolkits(self) -> List[str]:
        """Get list of toolkits that are stale and need refresh"""
        await self._ensure_engine()
        
        try:
            async with self.session_factory() as session:
                stale_query = text("""
                    SELECT toolkit_id 
                    FROM toolkits 
                    WHERE last_synced_at < NOW() - INTERVAL '24 hours'
                    AND is_deprecated = FALSE
                    ORDER BY last_synced_at ASC
                """)
                
                result = await session.execute(stale_query)
                stale_toolkits = [row[0] for row in result.fetchall()]
                return stale_toolkits
                
        except Exception as e:
            logger.error(f"Error getting stale toolkits: {e}")
            return []
    
    async def _refresh_stale_toolkits(self, toolkit_ids: List[str]) -> bool:
        """Refresh stale toolkits from external sources (MCP/SDK)"""
        # This would integrate with your existing MCP/SDK fetchers
        # For now, just update the last_synced_at timestamp
        logger.info(f"Refreshing {len(toolkit_ids)} stale toolkits from external sources")
        
        await self._ensure_engine()
        
        try:
            async with self.session_factory() as session:
                update_query = text("""
                    UPDATE toolkits 
                    SET last_synced_at = NOW() 
                    WHERE toolkit_id = ANY(:toolkit_ids)
                """)
                
                await session.execute(update_query, {"toolkit_ids": toolkit_ids})
                await session.commit()
                
                logger.info(f"Successfully updated last_synced_at for {len(toolkit_ids)} toolkits")
                return True
                
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
        """Get specific provider from database by slug"""
        await self._ensure_engine()
        
        try:
            async with self.session_factory() as session:
                # Get toolkit info by slug
                toolkit_query = text("""
                    SELECT 
                        toolkit_id, slug, name, description, website_url, category, 
                        version, created_at, updated_at, last_synced_at
                    FROM toolkits 
                    WHERE slug = :provider_slug AND is_deprecated = FALSE
                """)
                
                toolkit_result = await session.execute(toolkit_query, {"provider_slug": provider_slug})
                toolkit_row = toolkit_result.fetchone()
                
                if not toolkit_row:
                    return None
                
                # Get tools for this toolkit using the correct schema
                tools_query = text("""
                    SELECT 
                        tool_id, slug, name, display_name, description, tool_type, 
                        is_deprecated, version, input_schema, output_schema, tags,
                        created_at, updated_at
                    FROM tools
                    WHERE toolkit_id = :toolkit_id AND is_deprecated = FALSE
                    ORDER BY name
                """)
                
                tools_result = await session.execute(tools_query, {"toolkit_id": toolkit_row.toolkit_id})
                tools_data = []
                
                for row in tools_result.fetchall():
                    # Parse the input schema to extract parameters
                    parameters = []
                    if row.input_schema and isinstance(row.input_schema, dict):
                        properties = row.input_schema.get('properties', {})
                        required = row.input_schema.get('required', [])
                        
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
                    
                    tool = {
                        "slug": row.slug,
                        "name": row.name,
                        "display_name": row.display_name,
                        "description": row.description,
                        "tool_type": row.tool_type,
                        "version": row.version,
                        "parameters": parameters,
                        "input_schema": row.input_schema,
                        "output_schema": row.output_schema,
                        "tags": row.tags or []
                    }
                    tools_data.append(tool)
                
                # Convert to provider format
                provider = {
                    "id": toolkit_row.toolkit_id,
                    "slug": toolkit_row.slug,
                    "name": toolkit_row.name,
                    "description": toolkit_row.description,
                    "website": toolkit_row.website_url,
                    "category": toolkit_row.category,
                    "version": toolkit_row.version,
                    "created_at": toolkit_row.created_at,
                    "updated_at": toolkit_row.updated_at,
                    "last_synced_at": toolkit_row.last_synced_at,
                    "tools": tools_data
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
        await self._ensure_engine()
        
        try:
            async with self.session_factory() as session:
                # Build the query based on whether we're filtering by provider
                if provider_slug:
                    # Get tool from specific provider
                    tool_query = text("""
                        SELECT 
                            t.tool_id, t.slug, t.name, t.display_name, t.description, t.tool_type, t.version,
                            t.input_schema, t.output_schema, t.tags,
                            tk.slug as provider_slug, tk.name as provider_name
                        FROM tools t
                        JOIN toolkits tk ON t.toolkit_id = tk.toolkit_id
                        WHERE t.slug = :tool_slug 
                          AND tk.slug = :provider_slug 
                          AND t.is_deprecated = FALSE 
                          AND tk.is_deprecated = FALSE
                    """)
                    params = {"tool_slug": tool_slug, "provider_slug": provider_slug}
                else:
                    # Get tool from any provider
                    tool_query = text("""
                        SELECT 
                            t.tool_id, t.slug, t.name, t.display_name, t.description, t.tool_type, t.version,
                            t.input_schema, t.output_schema, t.tags,
                            tk.slug as provider_slug, tk.name as provider_name
                        FROM tools t
                        JOIN toolkits tk ON t.toolkit_id = tk.toolkit_id
                        WHERE t.slug = :tool_slug 
                          AND t.is_deprecated = FALSE 
                          AND tk.is_deprecated = FALSE
                        ORDER BY tk.slug
                    """)
                    params = {"tool_slug": tool_slug}
                
                tool_result = await session.execute(tool_query, params)
                tool_rows = tool_result.fetchall()
                
                if not tool_rows:
                    return None
                
                # Group by provider if not filtering by specific provider
                tools_by_provider = {}
                
                for row in tool_rows:
                    provider_slug = row.provider_slug
                    if provider_slug not in tools_by_provider:
                        # Parse the input schema to extract parameters
                        parameters = []
                        if row.input_schema and isinstance(row.input_schema, dict):
                            properties = row.input_schema.get('properties', {})
                            required = row.input_schema.get('required', [])
                            
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
                        
                        tools_by_provider[provider_slug] = {
                            "tool": {
                                "slug": row.slug,
                                "name": row.name,
                                "display_name": row.display_name,
                                "description": row.description,
                                "tool_type": row.tool_type,
                                "version": row.version,
                                "parameters": parameters,
                                "input_schema": row.input_schema,
                                "output_schema": row.output_schema,
                                "tags": row.tags or []
                            },
                            "provider": {
                                "slug": provider_slug,
                                "name": row.provider_name
                            }
                        }
                
                # If filtering by specific provider, return just that tool
                if provider_slug:
                    return tools_by_provider.get(provider_slug)
                
                # Otherwise return all providers that have this tool
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
        await self._ensure_engine()
        
        try:
            async with self.session_factory() as session:
                # Build the query based on whether we're filtering by provider
                if provider_slug:
                    # Get tool from specific provider
                    tool_query = text("""
                        SELECT 
                            t.tool_id, t.slug, t.name, t.display_name, t.description, t.tool_type, t.version,
                            t.input_schema, t.output_schema, t.tags,
                            tk.slug as provider_slug, tk.name as provider_name
                        FROM tools t
                        JOIN toolkits tk ON t.toolkit_id = tk.toolkit_id
                        WHERE t.name = :tool_name 
                          AND tk.slug = :provider_slug 
                          AND t.is_deprecated = FALSE 
                          AND tk.is_deprecated = FALSE
                    """)
                    params = {"tool_name": tool_name, "provider_slug": provider_slug}
                else:
                    # Get tool from any provider
                    tool_query = text("""
                        SELECT 
                            t.tool_id, t.slug, t.name, t.display_name, t.description, t.tool_type, t.version,
                            t.input_schema, t.output_schema, t.tags,
                            tk.slug as provider_slug, tk.name as provider_name
                        FROM tools t
                        JOIN toolkits tk ON t.toolkit_id = tk.toolkit_id
                        WHERE t.name = :tool_name 
                          AND t.is_deprecated = FALSE 
                          AND tk.is_deprecated = FALSE
                        ORDER BY tk.slug
                    """)
                    params = {"tool_name": tool_name}
                
                tool_result = await session.execute(tool_query, params)
                tool_rows = tool_result.fetchall()
                
                if not tool_rows:
                    return None
                
                # Group by provider if not filtering by specific provider
                tools_by_provider = {}
                
                for row in tool_rows:
                    provider_slug = row.provider_slug
                    if provider_slug not in tools_by_provider:
                        # Parse the input schema to extract parameters
                        parameters = []
                        if row.input_schema and isinstance(row.input_schema, dict):
                            properties = row.input_schema.get('properties', {})
                            required = row.input_schema.get('required', [])
                            
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
                        
                        tools_by_provider[provider_slug] = {
                            "tool": {
                                "slug": row.slug,
                                "name": row.name,
                                "display_name": row.display_name,
                                "description": row.description,
                                "tool_type": row.tool_type,
                                "version": row.version,
                                "parameters": parameters,
                                "input_schema": row.input_schema,
                                "output_schema": row.output_schema,
                                "tags": row.tags or []
                            },
                            "provider": {
                                "slug": provider_slug,
                                "name": row.provider_name
                            }
                        }
                
                # If filtering by specific provider, return just that tool
                if provider_slug:
                    return tools_by_provider.get(provider_slug)
                
                # Otherwise return all providers that have this tool
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
        await self._ensure_engine()
        
        try:
            async with self.session_factory() as session:
                # Build the base query
                base_query = """
                    SELECT 
                        t.tool_id, t.slug, t.name, t.display_name, t.description, t.tool_type, t.version,
                        t.input_schema, t.output_schema, t.tags,
                        tk.slug as provider_slug, tk.name as provider_name
                    FROM tools t
                    JOIN toolkits tk ON t.toolkit_id = tk.toolkit_id
                    WHERE t.is_deprecated = FALSE AND tk.is_deprecated = FALSE
                """
                
                params = {}
                conditions = []
                
                # Add provider filter if specified
                if provider_slug:
                    conditions.append("tk.slug = :provider_slug")
                    params["provider_slug"] = provider_slug
                
                # Add tool type filter if specified
                if tool_type:
                    conditions.append("t.tool_type = :tool_type")
                    params["tool_type"] = tool_type
                
                # Add search query if specified
                if query:
                    conditions.append("(t.name ILIKE :query OR t.display_name ILIKE :query OR t.description ILIKE :query)")
                    params["query"] = f"%{query}%"
                
                # Combine conditions
                if conditions:
                    base_query += " AND " + " AND ".join(conditions)
                
                # Add ordering and limit
                base_query += " ORDER BY tk.slug, t.name LIMIT :limit"
                params["limit"] = limit
                
                tool_result = await session.execute(text(base_query), params)
                tool_rows = tool_result.fetchall()
                
                # Group tools by provider
                tools_by_provider = {}
                
                for row in tool_rows:
                    provider_slug = row.provider_slug
                    if provider_slug not in tools_by_provider:
                        tools_by_provider[provider_slug] = {
                            "provider": {
                                "slug": provider_slug,
                                "name": row.provider_name
                            },
                            "tools": []
                        }
                    
                    tool = {
                        "slug": row.slug,
                        "name": row.name,
                        "display_name": row.display_name,
                        "description": row.description,
                        "tool_type": row.tool_type,
                        "version": row.version,
                        "input_schema": row.input_schema,
                        "output_schema": row.output_schema,
                        "tags": row.tags or []
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
