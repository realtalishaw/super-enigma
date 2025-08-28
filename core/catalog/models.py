from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum

# Parameter Types
class ParamType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    FILE = "file"

# Parameter Specifications
class ParamSpec(BaseModel):
    name: str
    type: ParamType
    description: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[List[str]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: Optional[str] = None  # regex pattern for strings
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    items: Optional['ParamSpec'] = None  # for array types
    properties: Optional[Dict[str, 'ParamSpec']] = None  # for object types

# Action Models
class ActionSpec(BaseModel):
    name: str
    description: str
    parameters: List[ParamSpec] = []
    returns: Optional[ParamSpec] = None
    rate_limit: Optional[str] = None
    timeout: Optional[int] = None  # seconds
    retry_policy: Optional[Dict[str, Any]] = None

# Trigger Models
class TriggerDelivery(str, Enum):
    WEBHOOK = "webhook"
    POLLING = "polling"
    STREAMING = "streaming"

class TriggerSpec(BaseModel):
    name: str
    description: str
    delivery: List[TriggerDelivery]
    parameters: List[ParamSpec] = []
    returns: Optional[ParamSpec] = None
    rate_limit: Optional[str] = None

# Scope and Permission Models
class ScopeLevel(str, Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"

class Scope(BaseModel):
    resource: str
    level: ScopeLevel
    description: Optional[str] = None

class Permission(BaseModel):
    name: str
    description: str
    scopes: List[Scope]

# Provider Models
class ProviderMetadata(BaseModel):
    name: str
    description: str
    website: Optional[str] = None
    logo_url: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []

class ProviderRateLimit(BaseModel):
    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None
    requests_per_day: Optional[int] = None
    burst_limit: Optional[int] = None

class Provider(BaseModel):
    id: str
    version: str = "1.0.0"
    metadata: ProviderMetadata
    actions: List[ActionSpec] = []
    triggers: List[TriggerSpec] = []
    permissions: List[Permission] = []
    rate_limits: Optional[ProviderRateLimit] = None
    authentication: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Catalog Response Models
class CatalogFilter(BaseModel):
    providers: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    has_actions: Optional[bool] = None
    has_triggers: Optional[bool] = None

class CatalogResponse(BaseModel):
    providers: List[Provider]
    total_count: int
    filters_applied: Optional[CatalogFilter] = None
    cached_at: Optional[datetime] = None
    source: Optional[str] = None  # "redis_cache", "external_fetchers", etc.

# Cache Models
class CatalogCache(BaseModel):
    data: CatalogResponse
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Update Models
class CatalogUpdate(BaseModel):
    provider_id: str
    action: str  # "add", "update", "remove"
    data: Optional[Provider] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
