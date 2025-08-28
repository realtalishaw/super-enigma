"""
Tool catalog management.
Provider, action, and parameter definitions with TTL caching.
"""

from .models import (
    # Core models
    Provider,
    ActionSpec,
    TriggerSpec,
    ParamSpec,
    ParamType,
    
    # Metadata models
    ProviderMetadata,
    ProviderRateLimit,
    
    # Permission models
    Permission,
    Scope,
    ScopeLevel,
    
    # Response models
    CatalogResponse,
    CatalogFilter,
    CatalogCache,
    CatalogUpdate,
    
    # Enums
    TriggerDelivery,
)

from .fetchers import (
    CatalogFetcher,
    ComposioMCPFetcher,
    ComposioSDKFetcher,
    CompositeFetcher,
)

from .service import CatalogService
from .database_service import DatabaseCatalogService
from .redis_client import RedisClientFactory
from .cache import RedisCacheStore

__all__ = [
    # Models
    "Provider",
    "ActionSpec", 
    "TriggerSpec",
    "ParamSpec",
    "ParamType",
    "ProviderMetadata",
    "ProviderRateLimit",
    "Permission",
    "Scope",
    "ScopeLevel",
    "CatalogResponse",
    "CatalogFilter",
    "CatalogCache",
    "CatalogUpdate",
    "TriggerDelivery",
    
    # Fetchers
    "CatalogFetcher",
    "ComposioMCPFetcher",
    "ComposioSDKFetcher", 
    "CompositeFetcher",
    
    # Services
    "CatalogService",
    "DatabaseCatalogService",  # Primary service - database-first with Redis cache
    
    # Redis Components
    "RedisClientFactory",
    "RedisCacheStore",
]

__version__ = "1.0.0"
