"""
Example usage of the Tool Catalog system

This script demonstrates how to:
1. Set up different fetchers (MCP, SDK, Composite)
2. Create a catalog service with caching
3. Fetch and filter catalog data
4. Search for providers
"""

import asyncio
import logging
from typing import List

from .fetchers import ComposioMCPFetcher, ComposioSDKFetcher, CompositeFetcher
from .service import CatalogService
from .models import CatalogFilter

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def demo_mcp_fetcher():
    """Demonstrate MCP fetcher usage"""
    logger.info("=== MCP Fetcher Demo ===")
    
    # Create MCP fetcher
    mcp_fetcher = ComposioMCPFetcher(
        mcp_endpoint="https://api.composio.com/mcp",
        api_key="your-api-key-here"
    )
    
    # Health check
    is_healthy = await mcp_fetcher.health_check()
    logger.info(f"MCP Fetcher health: {is_healthy}")
    
    # Fetch all providers
    providers = await mcp_fetcher.fetch_providers()
    logger.info(f"Found {len(providers)} providers from MCP")
    
    # Fetch specific provider
    if providers:
        provider = await mcp_fetcher.fetch_provider(providers[0].id)
        logger.info(f"Fetched provider: {provider.metadata.name if provider else 'Not found'}")
    
    return providers

async def demo_sdk_fetcher():
    """Demonstrate SDK fetcher usage"""
    logger.info("=== SDK Fetcher Demo ===")
    
    # Create SDK fetcher
    sdk_config = {
        "api_key": "your-sdk-key-here",
        "base_url": "https://api.composio.com/sdk",
        "timeout": 30
    }
    
    sdk_fetcher = ComposioSDKFetcher(sdk_config)
    
    # Health check
    is_healthy = await sdk_fetcher.health_check()
    logger.info(f"SDK Fetcher health: {is_healthy}")
    
    # Fetch all providers
    providers = await sdk_fetcher.fetch_providers()
    logger.info(f"Found {len(providers)} providers from SDK")
    
    return providers

async def demo_composite_fetcher():
    """Demonstrate composite fetcher usage"""
    logger.info("=== Composite Fetcher Demo ===")
    
    # Create individual fetchers
    mcp_fetcher = ComposioMCPFetcher("https://api.composio.com/mcp")
    sdk_fetcher = ComposioSDKFetcher({"api_key": "demo"})
    
    # Create composite fetcher
    composite_fetcher = CompositeFetcher([mcp_fetcher, sdk_fetcher])
    
    # Health check
    is_healthy = await composite_fetcher.health_check()
    logger.info(f"Composite Fetcher health: {is_healthy}")
    
    # Fetch all providers from all sources
    providers = await composite_fetcher.fetch_providers()
    logger.info(f"Found {len(providers)} total providers from all sources")
    
    return providers

async def demo_catalog_service():
    """Demonstrate catalog service usage with caching"""
    logger.info("=== Catalog Service Demo ===")
    
    # Create a composite fetcher
    mcp_fetcher = ComposioMCPFetcher("https://api.composio.com/mcp")
    sdk_fetcher = ComposioSDKFetcher({"api_key": "demo"})
    composite_fetcher = CompositeFetcher([mcp_fetcher, sdk_fetcher])
    
    # Create catalog service with 5-minute cache TTL
    catalog_service = CatalogService(
        fetcher=composite_fetcher,
        cache_ttl=300,  # 5 minutes
        max_cache_size=100
    )
    
    # Health check
    is_healthy = await catalog_service.health_check()
    logger.info(f"Catalog Service health: {is_healthy}")
    
    # Get all providers (will use cache after first fetch)
    catalog_response = await catalog_service.get_catalog()
    logger.info(f"Catalog contains {catalog_response.total_count} providers")
    
    # Get categories
    categories = await catalog_service.get_categories()
    logger.info(f"Available categories: {categories}")
    
    # Get tags
    tags = await catalog_service.get_tags()
    logger.info(f"Available tags: {tags[:10]}...")  # Show first 10 tags
    
    # Search for providers
    search_results = await catalog_service.search_providers("email", limit=5)
    logger.info(f"Search for 'email' found {len(search_results)} providers")
    
    # Filter by category
    communication_providers = await catalog_service.get_catalog(
        categories=["communication"]
    )
    logger.info(f"Communication providers: {communication_providers.total_count}")
    
    # Filter by tags
    email_providers = await catalog_service.get_catalog(
        tags=["email"]
    )
    logger.info(f"Email-related providers: {email_providers.total_count}")
    
    # Get cache statistics
    cache_stats = catalog_service.get_cache_stats()
    logger.info(f"Cache stats: {cache_stats}")
    
    return catalog_response

async def demo_filtering():
    """Demonstrate advanced filtering capabilities"""
    logger.info("=== Filtering Demo ===")
    
    # Create service
    mcp_fetcher = ComposioMCPFetcher("https://api.composio.com/mcp")
    catalog_service = CatalogService(fetcher=mcp_fetcher)
    
    # Create complex filter
    filter_params = CatalogFilter(
        categories=["communication"],
        has_actions=True,
        has_triggers=True
    )
    
    # Apply filter
    filtered_catalog = await catalog_service.get_catalog(
        categories=filter_params.categories,
        has_actions=filter_params.has_actions,
        has_triggers=filter_params.has_triggers
    )
    
    logger.info(f"Filtered catalog: {filtered_catalog.total_count} providers")
    
    # Show provider details
    for provider in filtered_catalog.providers[:3]:  # Show first 3
        logger.info(f"Provider: {provider.metadata.name}")
        logger.info(f"  Actions: {len(provider.actions)}")
        logger.info(f"  Triggers: {len(provider.triggers)}")
        logger.info(f"  Category: {provider.metadata.category}")
        logger.info(f"  Tags: {provider.metadata.tags}")

async def main():
    """Run all demos"""
    logger.info("Starting Tool Catalog Demo")
    
    try:
        # Run individual fetcher demos
        await demo_mcp_fetcher()
        await demo_sdk_fetcher()
        await demo_composite_fetcher()
        
        # Run service demo
        await demo_catalog_service()
        
        # Run filtering demo
        await demo_filtering()
        
        logger.info("All demos completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise

if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
