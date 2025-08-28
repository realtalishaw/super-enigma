# Tool Catalog System

The Tool Catalog system provides a comprehensive way to manage and access tool providers, their actions, triggers, and specifications. It's designed to be extensible and supports multiple data sources through a unified interface.

## Architecture

```
catalog/
├── models.py      # Data models for providers, actions, parameters, scopes
├── fetchers.py    # Data source fetchers (Composio MCP/SDK)
├── service.py     # Main service with TTL caching and filtering
├── example.py     # Usage examples and demos
└── __init__.py    # Package initialization and exports
```

## Key Components

### 1. Data Models (`models.py`)

- **Provider**: Complete provider information including metadata, actions, triggers, and permissions
- **ActionSpec**: Action definitions with parameters, return types, and rate limits
- **TriggerSpec**: Trigger definitions with delivery methods and parameters
- **ParamSpec**: Parameter specifications with validation rules
- **Scope & Permission**: OAuth scopes and permission management

### 2. Data Fetchers (`fetchers.py`)

- **CatalogFetcher**: Abstract base class for all fetchers
- **ComposioMCPFetcher**: Fetches data from Composio MCP endpoints
- **ComposioSDKFetcher**: Fetches data from Composio SDK
- **CompositeFetcher**: Combines multiple fetchers and deduplicates results

### 3. Catalog Service (`service.py`)

- **TTL Caching**: Configurable cache with automatic expiration
- **Filtering**: Support for provider, category, tag, and capability filtering
- **Search**: Full-text search across provider names, descriptions, and tags
- **Health Monitoring**: Health checks for fetchers and cache status

## Quick Start

### Basic Usage

```python
from app.core.catalog import CatalogService, ComposioMCPFetcher

# Create a fetcher
mcp_fetcher = ComposioMCPFetcher(
    mcp_endpoint="https://api.composio.com/mcp",
    api_key="your-api-key"
)

# Create the catalog service
catalog_service = CatalogService(
    fetcher=mcp_fetcher,
    cache_ttl=3600,  # 1 hour cache
    max_cache_size=1000
)

# Get all providers
catalog = await catalog_service.get_catalog()

# Get specific provider
provider = await catalog_service.get_provider("gmail")

# Search providers
results = await catalog_service.search_providers("email")
```

### Using Multiple Data Sources

```python
from app.core.catalog import (
    CatalogService, ComposioMCPFetcher, 
    ComposioSDKFetcher, CompositeFetcher
)

# Create multiple fetchers
mcp_fetcher = ComposioMCPFetcher("https://api.composio.com/mcp")
sdk_fetcher = ComposioSDKFetcher({"api_key": "your-key"})

# Combine them
composite_fetcher = CompositeFetcher([mcp_fetcher, sdk_fetcher])

# Use with service
catalog_service = CatalogService(fetcher=composite_fetcher)
```

### Filtering and Search

```python
# Filter by category
communication_providers = await catalog_service.get_catalog(
    categories=["communication"]
)

# Filter by tags
email_providers = await catalog_service.get_catalog(
    tags=["email", "gmail"]
)

# Filter by capabilities
providers_with_triggers = await catalog_service.get_catalog(
    has_triggers=True
)

# Search
search_results = await catalog_service.search_providers(
    "slack", limit=10
)
```

## Configuration

### Environment Variables

```bash
# MCP Configuration
COMPOSIO_MCP_ENDPOINT=https://api.composio.com/mcp
COMPOSIO_MCP_API_KEY=your-mcp-api-key

# SDK Configuration  
COMPOSIO_SDK_API_KEY=your-sdk-api-key
COMPOSIO_SDK_BASE_URL=https://api.composio.com/sdk

# Cache Configuration
CATALOG_CACHE_TTL=3600
CATALOG_MAX_CACHE_SIZE=1000
```

### Service Configuration

```python
catalog_service = CatalogService(
    fetcher=your_fetcher,
    cache_ttl=3600,           # Cache TTL in seconds
    max_cache_size=1000       # Maximum cache entries
)
```

## Advanced Features

### Custom Fetchers

You can create custom fetchers by implementing the `CatalogFetcher` interface:

```python
from app.core.catalog import CatalogFetcher

class CustomFetcher(CatalogFetcher):
    async def fetch_providers(self, filter_params=None):
        # Your custom implementation
        pass
    
    async def fetch_provider(self, provider_id):
        # Your custom implementation
        pass
    
    async def health_check(self):
        # Your custom implementation
        pass
```

### Cache Management

```python
# Get cache statistics
stats = catalog_service.get_cache_stats()

# Force refresh cache
await catalog_service.get_catalog(force_refresh=True)

# Health check
is_healthy = await catalog_service.health_check()
```

### Provider Details

```python
provider = await catalog_service.get_provider("gmail")

# Access provider information
print(f"Name: {provider.metadata.name}")
print(f"Category: {provider.metadata.category}")
print(f"Tags: {provider.metadata.tags}")

# List actions
for action in provider.actions:
    print(f"Action: {action.name}")
    print(f"Parameters: {len(action.parameters)}")

# List triggers
for trigger in provider.triggers:
    print(f"Trigger: {trigger.name}")
    print(f"Delivery: {trigger.delivery}")
```

## Error Handling

The system includes comprehensive error handling:

```python
try:
    catalog = await catalog_service.get_catalog()
except Exception as e:
    logger.error(f"Failed to fetch catalog: {e}")
    # Handle error appropriately
```

## Monitoring and Health Checks

```python
# Check overall health
is_healthy = await catalog_service.health_check()

# Get cache statistics
cache_stats = catalog_service.get_cache_stats()

# Monitor fetcher health
for fetcher in composite_fetcher.fetchers:
    health = await fetcher.health_check()
    print(f"{fetcher.__class__.__name__}: {health}")
```

## Performance Considerations

- **Caching**: TTL-based caching reduces API calls and improves response times
- **Async Operations**: All operations are asynchronous for better performance
- **Lazy Loading**: Data is fetched only when needed
- **Connection Pooling**: Fetchers can implement connection pooling for HTTP requests

## Testing

The system includes mock data for testing:

```python
# Mock providers are included in fetchers for development
mcp_fetcher = ComposioMCPFetcher("mock-endpoint")
providers = await mcp_fetcher.fetch_providers()
# Returns mock Gmail provider

sdk_fetcher = ComposioSDKFetcher({})
providers = await sdk_fetcher.fetch_providers()  
# Returns mock Slack provider
```

## Future Enhancements

- **Database Persistence**: Store catalog data in database for offline access
- **Real-time Updates**: WebSocket support for real-time catalog updates
- **Advanced Search**: Elasticsearch integration for better search capabilities
- **Rate Limiting**: Built-in rate limiting for API calls
- **Metrics**: Prometheus metrics for monitoring and alerting

## Contributing

When adding new features:

1. Update the data models in `models.py`
2. Implement new fetchers in `fetchers.py`
3. Add service methods in `service.py`
4. Update tests and examples
5. Update this documentation

## Support

For questions or issues, please refer to the main project documentation or create an issue in the project repository.
