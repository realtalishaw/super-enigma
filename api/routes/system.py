"""
System routes for health checks and system status.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2025-01-28T00:00:00Z",
        "version": "1.0.0"
    }


@router.get("/rate-limiting/status")
async def get_rate_limiting_status() -> Dict[str, Any]:
    """Get current rate limiting status for Claude API calls"""
    try:
        # Import here to avoid circular imports
        from services.dsl_generator.rate_limiter import get_global_rate_limiter
        
        rate_limiter = get_global_rate_limiter()
        stats = rate_limiter.get_stats()
        
        return {
            "status": "success",
            "rate_limiting": stats,
            "timestamp": "2025-01-28T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Failed to get rate limiting status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get rate limiting status: {str(e)}")


@router.post("/rate-limiting/configure")
async def configure_rate_limiting(config: Dict[str, Any]) -> Dict[str, Any]:
    """Configure rate limiting parameters"""
    try:
        from services.dsl_generator.rate_limiter import set_global_rate_limiter_config, RateLimitConfig
        
        # Extract configuration parameters
        rate_limit_config = RateLimitConfig(
            requests_per_minute=config.get("requests_per_minute", 20),
            burst_limit=config.get("burst_limit", 5),
            base_delay=config.get("base_delay", 2.0),
            max_delay=config.get("max_delay", 30.0),
            jitter_factor=config.get("jitter_factor", 0.25)
        )
        
        set_global_rate_limiter_config(rate_limit_config)
        
        return {
            "status": "success",
            "message": "Rate limiting configuration updated",
            "config": {
                "requests_per_minute": rate_limit_config.requests_per_minute,
                "burst_limit": rate_limit_config.burst_limit,
                "base_delay": rate_limit_config.base_delay,
                "max_delay": rate_limit_config.max_delay,
                "jitter_factor": rate_limit_config.jitter_factor
            },
            "timestamp": "2025-01-28T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Failed to configure rate limiting: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to configure rate limiting: {str(e)}")


@router.get("/ai-client/status")
async def get_ai_client_status() -> Dict[str, Any]:
    """Get AI client status and configuration"""
    try:
        from services.dsl_generator.ai_client import AIClient
        
        # Create a temporary client to get status
        client = AIClient()
        model_info = client.get_model_info()
        rate_stats = client.get_rate_limiting_stats()
        
        return {
            "status": "success",
            "ai_client": {
                "model_info": model_info,
                "rate_limiting_stats": rate_stats
            },
            "timestamp": "2025-01-28T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Failed to get AI client status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get AI client status: {str(e)}")
