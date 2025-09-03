#!/usr/bin/env python3
"""
Global cache service for the Weave API server.
This service preloads catalog data when the server starts and provides
access to cached data for all requests.
"""

import time
from typing import Dict, Any, Optional
from core.catalog import DatabaseCatalogService
from core.catalog.redis_client import RedisClientFactory
from core.catalog.cache import RedisCacheStore
from core.config import settings
from core.logging_config import get_logger

logger = get_logger(__name__)

class GlobalCacheService:
    """Global cache service that preloads catalog data on server startup"""
    
    def __init__(self):
        self._catalog_cache: Dict[str, Any] = {}
        self._catalog_cache_timestamp: Optional[float] = None
        self._catalog_cache_ttl: int = 3600  # 1 hour cache TTL
        self._redis_cache: Optional[RedisCacheStore] = None
        self._catalog_service: Optional[DatabaseCatalogService] = None
        self._initialized: bool = False
        self._initialization_error: Optional[str] = None
    
    async def initialize(self):
        """Initialize the global cache service and preload catalog data"""
        try:
            logger.info("🚀 Initializing Global Cache Service...")
            
            # Initialize Redis cache
            try:
                redis_client = await RedisClientFactory.get_client()
                self._redis_cache = RedisCacheStore(redis_client)
                logger.info("✅ Redis cache initialized successfully")
            except Exception as e:
                logger.warning(f"⚠️  Redis cache initialization failed: {e}")
                logger.info("Continuing without Redis cache (limited functionality)")
                self._redis_cache = None
            
            # Initialize catalog service
            try:
                from database.config import get_database_url
                self._catalog_service = DatabaseCatalogService(
                    database_url=get_database_url(),
                    redis_cache=self._redis_cache or None
                )
                logger.info("✅ Database catalog service initialized successfully")
            except Exception as e:
                logger.warning(f"⚠️  Database catalog service initialization failed: {e}")
                logger.info("Continuing without catalog service (limited functionality)")
                self._catalog_service = None
            
            # Preload catalog cache for immediate use
            if self._catalog_service:
                await self._preload_catalog_cache()
            
            self._initialized = True
            logger.info("🎉 Global Cache Service initialized successfully")
            
        except Exception as e:
            self._initialization_error = str(e)
            logger.error(f"❌ Failed to initialize Global Cache Service: {e}")
            # Don't raise - allow service to continue in limited mode
    
    async def _preload_catalog_cache(self):
        """Preload catalog cache during initialization for immediate use"""
        try:
            logger.info("📚 Preloading catalog cache...")
            catalog_data = await self._catalog_service.get_catalog()
            providers = catalog_data.get('providers', {})
            
            # Handle case where providers might be a list or dict
            if isinstance(providers, list):
                providers_dict = {p.get('slug', f'provider_{i}'): p for i, p in enumerate(providers)}
                providers = providers_dict
            elif not isinstance(providers, dict):
                providers = {}
            
            # Cache the data
            self._catalog_cache = providers
            self._catalog_cache_timestamp = time.time()
            
            logger.info(f"✅ Catalog cache preloaded with {len(providers)} providers")
            
            # Log some sample providers for debugging
            if providers:
                sample_providers = list(providers.keys())[:3]
                logger.info(f"Sample providers: {', '.join(sample_providers)}")
                
                # Log some sample actions and triggers
                for provider_key in sample_providers:
                    provider = providers[provider_key]
                    actions_count = len(provider.get('actions', []))
                    triggers_count = len(provider.get('triggers', []))
                    logger.info(f"  {provider_key}: {actions_count} actions, {triggers_count} triggers")
            
        except Exception as e:
            logger.error(f"❌ Failed to preload catalog cache: {e}")
            # Don't fail initialization, just log the error
            self._catalog_cache = {}
            self._catalog_cache_timestamp = None
    
    def get_catalog_cache(self) -> Dict[str, Any]:
        """Get the cached catalog data"""
        return self._catalog_cache.copy()
    
    def get_catalog_service(self) -> Optional[DatabaseCatalogService]:
        """Get the catalog service instance"""
        return self._catalog_service
    
    def get_redis_cache(self) -> Optional[RedisCacheStore]:
        """Get the Redis cache instance"""
        return self._redis_cache
    
    def is_initialized(self) -> bool:
        """Check if the cache service is initialized"""
        return self._initialized
    
    def get_initialization_error(self) -> Optional[str]:
        """Get the initialization error if any"""
        return self._initialization_error
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get the current cache status"""
        current_time = time.time()
        if self._catalog_cache_timestamp:
            age_seconds = current_time - self._catalog_cache_timestamp
            ttl_remaining = max(0, self._catalog_cache_ttl - age_seconds)
            is_valid = age_seconds < self._catalog_cache_ttl
        else:
            age_seconds = None
            ttl_remaining = None
            is_valid = False
        
        return {
            "initialized": self._initialized,
            "has_cached_data": bool(self._catalog_cache),
            "cache_age_seconds": age_seconds,
            "ttl_remaining_seconds": ttl_remaining,
            "is_valid": is_valid,
            "provider_count": len(self._catalog_cache) if self._catalog_cache else 0,
            "catalog_service_available": self._catalog_service is not None,
            "redis_cache_available": self._redis_cache is not None,
            "cache_preloaded": bool(self._catalog_cache and self._catalog_cache_timestamp),
            "initialization_error": self._initialization_error
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of the cache service"""
        cache_status = self.get_cache_status()
        
        # Determine overall health
        is_healthy = (
            self._initialized and
            cache_status.get('has_cached_data', False) and
            cache_status.get('cache_preloaded', False)
        )
        
        return {
            "healthy": is_healthy,
            "cache_status": cache_status,
            "ready_for_requests": is_healthy and cache_status.get('provider_count', 0) > 0
        }
    
    async def refresh_cache(self, force: bool = False):
        """Refresh the catalog cache data"""
        if not self._catalog_service:
            logger.warning("Cannot refresh cache: catalog service not available")
            return
        
        if force or not self._catalog_cache:
            logger.info("🔄 Refreshing catalog cache data")
            await self._preload_catalog_cache()
        else:
            logger.info("Cache is still valid, no refresh needed")
    
    def clear_cache(self):
        """Clear the in-memory catalog cache"""
        self._catalog_cache = {}
        self._catalog_cache_timestamp = None
        logger.info("🗑️  In-memory catalog cache cleared")
    
    def get_catalog_statistics(self) -> Dict[str, Any]:
        """Get detailed catalog statistics"""
        if not self._catalog_cache:
            return {"error": "No catalog data available"}
        
        # Count providers by category
        categories = {}
        for provider in self._catalog_cache.values():
            category = provider.get('category', 'Unknown')
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        # Count total tools
        total_triggers = 0
        total_actions = 0
        providers_with_triggers = 0
        providers_with_actions = 0
        valid_providers = 0
        
        for provider in self._catalog_cache.values():
            triggers = provider.get('triggers', [])
            actions = provider.get('actions', [])
            
            total_triggers += len(triggers)
            total_actions += len(actions)
            
            if triggers:
                providers_with_triggers += 1
            if actions:
                providers_with_actions += 1
            if triggers and actions:
                valid_providers += 1
        
        # Get top providers by tool count
        provider_stats = []
        for slug, provider in self._catalog_cache.items():
            provider_stats.append({
                "slug": slug,
                "name": provider.get('name', slug),
                "category": provider.get('category', 'Unknown'),
                "triggers_count": len(provider.get('triggers', [])),
                "actions_count": len(provider.get('actions', [])),
                "total_tools": len(provider.get('triggers', [])) + len(provider.get('actions', []))
            })
        
        # Sort by total tools and get top 20
        provider_stats.sort(key=lambda x: x['total_tools'], reverse=True)
        top_providers = provider_stats[:20]
        
        return {
            "total_providers": len(self._catalog_cache),
            "total_triggers": total_triggers,
            "total_actions": total_actions,
            "providers_with_triggers": providers_with_triggers,
            "providers_with_actions": providers_with_actions,
            "valid_providers": valid_providers,
            "categories": categories,
            "top_providers": top_providers,
            "average_tools_per_provider": (total_triggers + total_actions) / len(self._catalog_cache) if self._catalog_cache else 0,
            "catalog_quality": "good" if valid_providers > len(self._catalog_cache) * 0.5 else "poor"
        }

# Global instance
global_cache_service = GlobalCacheService()

async def get_global_cache_service() -> GlobalCacheService:
    """Get the global cache service instance"""
    return global_cache_service
