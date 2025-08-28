import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import hashlib

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, timedelta):
            return obj.total_seconds()
        return super().default(obj)


class RedisCacheStore:
    """Redis-based cache store for performance optimization - not for data storage"""
    
    def __init__(self, redis_client: Redis, key_prefix: str = "catalog_cache"):
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.default_ttl = 3600  # 1 hour default
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache by key"""
        try:
            cache_key = f"{self.key_prefix}:{key}"
            data = await self.redis.get(cache_key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting from Redis cache: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL"""
        try:
            cache_key = f"{self.key_prefix}:{key}"
            # Use custom encoder to handle datetime objects
            data = json.dumps(value, cls=DateTimeEncoder)
            ttl = ttl or self.default_ttl
            
            await self.redis.setex(cache_key, ttl, data)
            return True
        except Exception as e:
            logger.error(f"Error setting in Redis cache: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            cache_key = f"{self.key_prefix}:{key}"
            await self.redis.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"Error deleting from Redis cache: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            cache_key = f"{self.key_prefix}:{key}"
            return await self.redis.exists(cache_key) > 0
        except Exception as e:
            logger.error(f"Error checking key existence in Redis cache: {e}")
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for a key"""
        try:
            cache_key = f"{self.key_prefix}:{key}"
            return await self.redis.expire(cache_key, ttl)
        except Exception as e:
            logger.error(f"Error setting expiration in Redis cache: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check Redis health"""
        try:
            await self.redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    async def clear_all(self) -> bool:
        """Clear all cache entries"""
        try:
            pattern = f"{self.key_prefix}:*"
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Error clearing Redis cache: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            pattern = f"{self.key_prefix}:*"
            keys = await self.redis.keys(pattern)
            
            # Get memory usage for cache keys
            total_memory = 0
            for key in keys:
                try:
                    memory = await self.redis.memory_usage(key)
                    if memory:
                        total_memory += memory
                except:
                    pass
            
            return {
                "total_keys": len(keys),
                "total_memory_bytes": total_memory,
                "prefix": self.key_prefix,
                "default_ttl": self.default_ttl
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}