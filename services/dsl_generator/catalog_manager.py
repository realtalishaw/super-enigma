"""
Catalog Manager for DSL Generator

Handles catalog data management, caching, validation, and provides
catalog context for workflow generation.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from core.catalog import DatabaseCatalogService
from core.catalog.redis_client import RedisClientFactory
from core.catalog.cache import RedisCacheStore
from core.config import settings

logger = logging.getLogger(__name__)


class CatalogManager:
    """
    Manages catalog data for the DSL generator service.
    
    Responsibilities:
    - Catalog data caching and refresh
    - Catalog validation and health checks
    - Providing catalog context for generation
    - Managing catalog service connections
    """
    
    def __init__(self):
        """Initialize the catalog manager"""
        self.catalog_service = None
        self.redis_cache = None
        
        # In-memory cache for catalog data
        self._catalog_cache = {}
        self._catalog_cache_timestamp = None
        self._catalog_cache_ttl = 3600  # 1 hour cache TTL
    
    async def initialize(self):
        """Initialize catalog service and Redis cache"""
        try:
            # Initialize Redis cache
            try:
                redis_client = await RedisClientFactory.get_client()
                self.redis_cache = RedisCacheStore(redis_client)
                logger.info("Redis cache initialized successfully")
            except Exception as e:
                logger.warning(f"Redis cache initialization failed: {e}")
                logger.info("Continuing without Redis cache (limited functionality)")
                self.redis_cache = None
            
            # Initialize catalog service
            try:
                from database.config import get_database_url
                self.catalog_service = DatabaseCatalogService(
                    database_url=get_database_url(),
                    redis_cache=self.redis_cache or None
                )
                logger.info("Database catalog service initialized successfully")
            except Exception as e:
                logger.warning(f"Database catalog service initialization failed: {e}")
                logger.info("Continuing without catalog service (limited validation)")
                self.catalog_service = None
            
            logger.info("Catalog manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize catalog manager: {e}")
            self.redis_cache = None
            self.catalog_service = None
    
    def set_global_cache(self, catalog_cache: Dict[str, Any]):
        """Set the catalog cache from the global cache service"""
        if catalog_cache:
            self._catalog_cache = catalog_cache.copy()
            self._catalog_cache_timestamp = time.time()
            logger.info(f"✅ Catalog manager loaded with {len(catalog_cache)} providers from global cache")
        else:
            logger.warning("⚠️  No catalog cache provided to catalog manager")
    
    async def get_catalog_data(self) -> Dict[str, Any]:
        """Get catalog data from cache or fetch if needed"""
        current_time = time.time()
        
        # Check if we have valid cached data
        if (self._catalog_cache and 
            self._catalog_cache_timestamp and 
            (current_time - self._catalog_cache_timestamp) < self._catalog_cache_ttl):
            age_seconds = current_time - self._catalog_cache_timestamp
            logger.info(f"Cache HIT: Using in-memory cached catalog data (age: {age_seconds:.1f}s, {len(self._catalog_cache)} providers)")
            return self._catalog_cache
        
        # Cache miss or expired - fetch fresh data
        if self.catalog_service:
            try:
                logger.info("Cache MISS: Fetching fresh catalog data from service")
                catalog_data = await self.catalog_service.get_catalog()
                providers = catalog_data.get('providers', {})
                
                # Handle case where providers might be a list or dict
                if isinstance(providers, list):
                    providers_dict = {p.get('slug', f'provider_{i}'): p for i, p in enumerate(providers)}
                    providers = providers_dict
                elif not isinstance(providers, dict):
                    providers = {}
                
                # Cache the data
                self._catalog_cache = providers
                self._catalog_cache_timestamp = current_time
                
                logger.info(f"Cache UPDATED: Cached catalog data with {len(providers)} providers (TTL: {self._catalog_cache_ttl}s)")
                return providers
                
            except Exception as e:
                logger.warning(f"Failed to fetch catalog data: {e}")
                return {}
        else:
            logger.info("No catalog service available - using empty catalog")
            return {}
    
    async def preload_catalog_cache(self):
        """Preload catalog cache during initialization for immediate use"""
        try:
            logger.info("Preloading catalog cache...")
            catalog_data = await self.catalog_service.get_catalog()
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
            logger.error(f"Failed to preload catalog cache: {e}")
            self._catalog_cache = {}
            self._catalog_cache_timestamp = None
    
    def clear_catalog_cache(self):
        """Clear the in-memory catalog cache"""
        self._catalog_cache = {}
        self._catalog_cache_timestamp = None
        logger.info("In-memory catalog cache cleared")
    
    async def refresh_catalog_cache(self, force: bool = False):
        """Refresh the catalog cache data"""
        if force or not self._catalog_cache:
            logger.info("Refreshing catalog cache data")
            self.clear_catalog_cache()
            await self.get_catalog_data()
        else:
            logger.info("Cache is still valid, no refresh needed")
    
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
            "has_cached_data": bool(self._catalog_cache),
            "cache_age_seconds": age_seconds,
            "ttl_remaining_seconds": ttl_remaining,
            "is_valid": is_valid,
            "provider_count": len(self._catalog_cache) if self._catalog_cache else 0,
            "catalog_service_available": self.catalog_service is not None,
            "redis_cache_available": self.redis_cache is not None,
            "cache_preloaded": bool(self._catalog_cache and self._catalog_cache_timestamp)
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of the catalog manager"""
        cache_status = self.get_cache_status()
        catalog_summary = self.get_catalog_summary()
        
        # Determine overall health
        is_healthy = (
            cache_status.get('catalog_service_available', False) and
            cache_status.get('has_cached_data', False) and
            cache_status.get('cache_preloaded', False)
        )
        
        return {
            "healthy": is_healthy,
            "cache_status": cache_status,
            "catalog_summary": catalog_summary,
            "ready_for_generation": is_healthy and cache_status.get('provider_count', 0) > 0
        }
    
    def get_catalog_summary(self) -> Dict[str, Any]:
        """Get a summary of available catalog data"""
        if not self._catalog_cache:
            return {"error": "No catalog data available"}
        
        # Count available tools
        total_triggers = sum(len(p.get('triggers', [])) for p in self._catalog_cache.values())
        total_actions = sum(len(p.get('actions', [])) for p in self._catalog_cache.values())
        
        # Get sample toolkits
        sample_toolkits = list(self._catalog_cache.keys())[:5]
        
        # Get sample triggers and actions
        sample_triggers = []
        sample_actions = []
        
        for provider in list(self._catalog_cache.values())[:3]:
            if 'triggers' in provider:
                sample_triggers.extend([t.get('name', 'Unknown') for t in provider['triggers'][:2]])
            if 'actions' in provider:
                sample_actions.extend([a.get('name', 'Unknown') for a in provider['actions'][:2]])
        
        return {
            "total_providers": len(self._catalog_cache),
            "total_triggers": total_triggers,
            "total_actions": total_actions,
            "sample_toolkits": sample_toolkits,
            "sample_triggers": sample_triggers[:5],
            "sample_actions": sample_actions[:5],
            "cache_timestamp": self._catalog_cache_timestamp
        }
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider slugs"""
        return list(self._catalog_cache.keys()) if self._catalog_cache else []
    
    def get_provider_actions(self, provider_slug: str) -> List[str]:
        """Get list of available actions for a specific provider"""
        if not self._catalog_cache or provider_slug not in self._catalog_cache:
            return []
        
        provider = self._catalog_cache[provider_slug]
        return [action.get('name', 'Unknown') for action in provider.get('actions', [])]
    
    def get_provider_triggers(self, provider_slug: str) -> List[str]:
        """Get list of available triggers for a specific provider"""
        if not self._catalog_cache or provider_slug not in self._catalog_cache:
            return []
        
        provider = self._catalog_cache[provider_slug]
        return [trigger.get('name', 'Unknown') for trigger in provider.get('triggers', [])]
    
    def validate_catalog_references(self, providers: List[str], actions: List[str], triggers: List[str]) -> Dict[str, Any]:
        """Validate if the provided references exist in the catalog"""
        if not self._catalog_cache:
            return {
                "valid": False,
                "error": "No catalog data available",
                "missing_providers": providers,
                "missing_actions": actions,
                "missing_triggers": triggers
            }
        
        available_providers = set(self._catalog_cache.keys())
        available_actions = set()
        available_triggers = set()
        
        # Collect all available actions and triggers from all providers
        for provider in self._catalog_cache.values():
            for action in provider.get('actions', []):
                available_actions.add(action.get('name', ''))
            for trigger in provider.get('triggers', []):
                available_triggers.add(trigger.get('name', ''))
        
        # Check what's missing
        missing_providers = [p for p in providers if p not in available_providers]
        missing_actions = [a for a in actions if a not in available_actions]
        missing_triggers = [t for t in triggers if t not in available_triggers]
        
        is_valid = not (missing_providers or missing_actions or missing_triggers)
        
        return {
            "valid": is_valid,
            "missing_providers": missing_providers,
            "missing_actions": missing_actions,
            "missing_triggers": missing_triggers,
            "available_providers_count": len(available_providers),
            "available_actions_count": len(available_actions),
            "available_triggers_count": len(available_triggers)
        }
    
    def extract_triggers(self, providers: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract available triggers from providers"""
        triggers = []
        if not providers:
            logger.warning("No providers provided to extract_triggers")
            return triggers
        
        logger.debug(f"Extracting triggers from {len(providers)} providers")
        logger.debug(f"Provider keys: {list(providers.keys())[:5]}...")  # Show first 5 keys
        
        for provider_key, provider in providers.items():
            logger.debug(f"Processing provider: {provider_key}")
            if 'triggers' in provider:
                triggers_count = len(provider['triggers'])
                logger.debug(f"  Found {triggers_count} triggers in provider {provider_key}")
                
                for trigger in provider['triggers']:
                    # Use slug as the primary identifier (matches database structure)
                    trigger_slug = trigger.get('slug') or f"trigger_{len(triggers)}"
                    
                    trigger_info = {
                        'id': trigger.get('id'),  # Keep original id if it exists
                        'name': trigger.get('name'),
                        'type': trigger.get('type'),
                        'slug': trigger_slug,  # Use slug as primary identifier
                        'toolkit_slug': provider.get('slug'),
                        'toolkit_name': provider.get('name'),
                        'description': trigger.get('description', ''),
                        'parameters': trigger.get('parameters', [])
                    }
                    triggers.append(trigger_info)
            else:
                logger.debug(f"  No triggers found in provider {provider_key}")
        
        logger.info(f"Extracted {len(triggers)} triggers from {len(providers)} providers")
        if triggers:
            logger.debug(f"Sample trigger structure: {triggers[0]}")
        else:
            logger.warning("No triggers were extracted from any providers")
        
        return triggers
    
    def extract_actions(self, providers: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract available actions from providers"""
        actions = []
        if not providers:
            logger.warning("No providers provided to extract_actions")
            return actions
        
        logger.debug(f"Extracting actions from {len(providers)} providers")
        logger.debug(f"Provider keys: {list(providers.keys())[:5]}...")  # Show first 5 keys
        
        for provider_key, provider in providers.items():
            logger.debug(f"Processing provider: {provider_key}")
            if 'actions' in provider:
                actions_count = len(provider['actions'])
                logger.debug(f"  Found {actions_count} actions in provider {provider_key}")
                
                for action in provider['actions']:
                    # Use slug as the primary identifier (matches database structure)
                    action_slug = action.get('slug') or f"action_{len(actions)}"
                    
                    action_info = {
                        'id': action.get('id'),
                        'name': action.get('name'),
                        'action_name': action.get('action_name'),  # Keep original action_name if it exists
                        'slug': action_slug,  # Use slug as primary identifier
                        'toolkit_slug': provider.get('slug'),
                        'toolkit_name': provider.get('name'),
                        'description': action.get('description', ''),
                        'parameters': action.get('parameters', [])
                    }
                    actions.append(action_info)
            else:
                logger.debug(f"  No actions found in provider {provider_key}")
        
        logger.info(f"Extracted {len(actions)} actions from {len(providers)} providers")
        if actions:
            logger.debug(f"Sample action structure: {actions[0]}")
        else:
            logger.warning("No actions were extracted from any providers")
        
        return actions
    
    def extract_categories(self, providers: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract provider categories"""
        categories = {}
        if not providers:
            return list(categories.values())
            
        for provider in providers.values():
            if 'categories' in provider:
                for category in provider['categories']:
                    cat_id = category.get('id')
                    if cat_id not in categories:
                        categories[cat_id] = {
                            'id': cat_id,
                            'name': category.get('name'),
                            'providers': []
                        }
                    categories[cat_id]['providers'].append(provider.get('slug'))
        
        return list(categories.values())
    
    def check_catalog_sufficiency(self) -> Dict[str, Any]:
        """Check if the catalog has sufficient data to generate meaningful workflows"""
        if not self._catalog_cache:
            return {
                'sufficient': False,
                'reason': 'No providers available in catalog'
            }
        
        # Count available actions
        total_actions = sum(len(p.get('actions', [])) for p in self._catalog_cache.values())
        
        if total_actions == 0:
            return {
                'sufficient': False,
                'reason': 'No actions available in catalog'
            }
        
        # Check minimum requirements
        min_providers = 1
        min_actions = 1
        
        if len(self._catalog_cache) < min_providers:
            return {
                'sufficient': False,
                'reason': f'Insufficient providers: {len(self._catalog_cache)} < {min_providers}'
            }
        
        if total_actions < min_actions:
            return {
                'sufficient': False,
                'reason': f'Insufficient actions: {total_actions} < {min_actions}'
            }
        
        return {
            'sufficient': True,
            'reason': 'Catalog has sufficient data',
            'provider_count': len(self._catalog_cache),
            'action_count': total_actions
        }
