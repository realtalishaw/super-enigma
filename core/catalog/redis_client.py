import asyncio
import logging
from typing import Optional
from redis.asyncio import Redis, ConnectionPool
from core.config import settings

logger = logging.getLogger(__name__)

class RedisClientFactory:
    """Factory for creating and managing Redis connections"""
    
    _redis_client: Optional[Redis] = None
    _connection_pool: Optional[ConnectionPool] = None
    
    @classmethod
    async def get_client(cls) -> Redis:
        """Get or create Redis client singleton"""
        if cls._redis_client is None:
            cls._redis_client = await cls._create_client()
        return cls._redis_client
    
    @classmethod
    async def _create_client(cls) -> Redis:
        """Create new Redis client"""
        try:
            # Create connection pool
            cls._connection_pool = ConnectionPool.from_url(
                settings.redis_url,
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True
            )
            
            # Create Redis client
            client = Redis(connection_pool=cls._connection_pool)
            
            # Test connection
            await client.ping()
            logger.info("Redis connection established successfully")
            
            return client
            
        except Exception as e:
            logger.error(f"Failed to create Redis client: {e}")
            raise
    
    @classmethod
    async def close_client(cls) -> None:
        """Close Redis client and connection pool"""
        if cls._redis_client:
            await cls._redis_client.close()
            cls._redis_client = None
        
        if cls._connection_pool:
            await cls._connection_pool.disconnect()
            cls._connection_pool = None
        
        logger.info("Redis client closed")
    
    @classmethod
    async def health_check(cls) -> bool:
        """Check Redis connection health"""
        try:
            client = await cls.get_client()
            await client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
