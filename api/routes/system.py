"""
System routes for health checks and system status.
"""

from fastapi import APIRouter, Depends
from api.cache_service import get_global_cache_service

router = APIRouter(prefix="", tags=["System"])


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": "2024-01-15T10:00:00Z"}


@router.get("/health/cache")
async def cache_health_check(cache_service = Depends(get_global_cache_service)):
    """Cache health check endpoint"""
    if not cache_service:
        return {
            "status": "error",
            "message": "Cache service not available",
            "timestamp": "2024-01-15T10:00:00Z"
        }
    
    cache_status = cache_service.get_cache_status()
    health_status = cache_service.get_health_status()
    
    return {
        "status": "success",
        "cache": cache_status,
        "health": health_status,
        "timestamp": "2024-01-15T10:00:00Z"
    }


@router.get("/cache/status")
async def cache_status(cache_service = Depends(get_global_cache_service)):
    """Get detailed cache status"""
    if not cache_service:
        return {
            "status": "error",
            "message": "Cache service not available"
        }
    
    return {
        "status": "success",
        "cache": cache_service.get_cache_status(),
        "health": cache_service.get_health_status()
    }


@router.post("/cache/refresh")
async def refresh_cache(cache_service = Depends(get_global_cache_service)):
    """Refresh the catalog cache"""
    if not cache_service:
        return {
            "status": "error",
            "message": "Cache service not available"
        }
    
    try:
        await cache_service.refresh_cache(force=True)
        return {
            "status": "success",
            "message": "Cache refreshed successfully"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to refresh cache: {e}"
        }


@router.get("/cache/info")
async def cache_info(cache_service = Depends(get_global_cache_service)):
    """Get information about what's in the cache"""
    if not cache_service:
        return {
            "status": "error",
            "message": "Cache service not available"
        }
    
    try:
        catalog_cache = cache_service.get_catalog_cache()
        
        if not catalog_cache:
            return {
                "status": "success",
                "message": "Cache is empty",
                "data": {}
            }
        
        # Get sample providers
        sample_providers = list(catalog_cache.keys())[:10]
        sample_data = {}
        
        for provider_key in sample_providers:
            provider = catalog_cache[provider_key]
            sample_data[provider_key] = {
                "name": provider.get('name', provider_key),
                "category": provider.get('category', 'Unknown'),
                "triggers_count": len(provider.get('triggers', [])),
                "actions_count": len(provider.get('actions', [])),
                "sample_triggers": [t.get('name', 'Unknown') for t in provider.get('triggers', [])[:3]],
                "sample_actions": [a.get('name', 'Unknown') for a in provider.get('actions', [])[:3]]
            }
        
        return {
            "status": "success",
            "total_providers": len(catalog_cache),
            "sample_providers": sample_data,
            "cache_timestamp": cache_service.get_cache_status().get('cache_age_seconds', 0)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get cache info: {e}"
        }


@router.get("/cache/statistics")
async def cache_statistics(cache_service = Depends(get_global_cache_service)):
    """Get detailed catalog statistics"""
    if not cache_service:
        return {
            "status": "error",
            "message": "Cache service not available"
        }
    
    try:
        stats = cache_service.get_catalog_statistics()
        return {
            "status": "success",
            "statistics": stats
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get cache statistics: {e}"
        }
