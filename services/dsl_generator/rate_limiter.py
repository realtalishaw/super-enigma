"""
Rate Limiter for Claude API Calls

Provides centralized rate limiting to prevent overwhelming the Claude API
and ensure fair usage across all components of the system.
"""

import asyncio
import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from collections import deque
import random

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    requests_per_minute: int = 20  # Default: 20 requests per minute
    burst_limit: int = 5  # Allow burst of 5 requests
    base_delay: float = 2.0  # Base delay between requests
    max_delay: float = 30.0  # Maximum delay between requests
    jitter_factor: float = 0.25  # ±25% random variation


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for Claude API calls.
    
    This implementation uses a sliding window approach with token bucket
    semantics to ensure fair and predictable rate limiting.
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = config.burst_limit
        self.last_refill = time.time()
        self.request_times = deque(maxlen=config.requests_per_minute)
        self.lock = asyncio.Lock()
        
        # Rate limiting state
        self.total_requests = 0
        self.rate_limited_requests = 0
        self.last_rate_limit_time = 0
    
    async def acquire_token(self, wait: bool = True) -> bool:
        """
        Acquire a token for making a request.
        
        Args:
            wait: If True, wait until a token is available. If False, return immediately.
            
        Returns:
            True if token acquired, False if no token available and wait=False
        """
        async with self.lock:
            current_time = time.time()
            
            # Refill tokens based on time passed
            self._refill_tokens(current_time)
            
            if self.tokens > 0:
                self.tokens -= 1
                self.total_requests += 1
                self.request_times.append(current_time)
                return True
            
            if not wait:
                return False
            
            # Calculate wait time until next token is available
            wait_time = self._calculate_wait_time(current_time)
            
            # Add jitter to prevent thundering herd
            jitter = random.uniform(1 - self.config.jitter_factor, 1 + self.config.jitter_factor)
            wait_time *= jitter
            
            logger.info(f"Rate limit hit, waiting {wait_time:.2f}s for next token")
            await asyncio.sleep(wait_time)
            
            # Try again after waiting
            return await self.acquire_token(wait=False)
    
    def _refill_tokens(self, current_time: float):
        """Refill tokens based on time passed"""
        time_passed = current_time - self.last_refill
        tokens_to_add = (time_passed / 60.0) * self.config.requests_per_minute
        
        self.tokens = min(
            self.config.burst_limit,
            self.tokens + tokens_to_add
        )
        self.last_refill = current_time
    
    def _calculate_wait_time(self, current_time: float) -> float:
        """Calculate wait time until next token is available"""
        # Find the oldest request in the sliding window
        if self.request_times:
            oldest_request = self.request_times[0]
            time_since_oldest = current_time - oldest_request
            
            # If we haven't made enough requests in the last minute, we can make one now
            if time_since_oldest >= 60.0:
                return 0.0
            
            # Calculate time until we can make the next request
            return 60.0 - time_since_oldest
        
        return 0.0
    
    async def wait_for_token(self) -> None:
        """Wait until a token is available"""
        await self.acquire_token(wait=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current rate limiting statistics"""
        current_time = time.time()
        return {
            "config": {
                "requests_per_minute": self.config.requests_per_minute,
                "burst_limit": self.config.burst_limit,
                "base_delay": self.config.base_delay,
                "max_delay": self.config.max_delay
            },
            "current_state": {
                "available_tokens": self.tokens,
                "total_requests": self.total_requests,
                "rate_limited_requests": self.rate_limited_requests,
                "requests_in_window": len(self.request_times)
            },
            "timing": {
                "last_refill": self.last_refill,
                "time_since_last_refill": current_time - self.last_refill,
                "last_rate_limit": self.last_rate_limit_time,
                "time_since_last_rate_limit": current_time - self.last_rate_limit_time if self.last_rate_limit_time > 0 else None
            }
        }


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts limits based on API response patterns.
    
    This limiter learns from 429 responses and adjusts the rate limiting
    parameters to optimize throughput while avoiding rate limits.
    """
    
    def __init__(self, initial_config: RateLimitConfig):
        self.base_config = initial_config
        self.current_config = RateLimitConfig(
            requests_per_minute=initial_config.requests_per_minute,
            burst_limit=initial_config.burst_limit,
            base_delay=initial_config.base_delay,
            max_delay=initial_config.max_delay,
            jitter_factor=initial_config.jitter_factor
        )
        
        self.rate_limiter = TokenBucketRateLimiter(self.current_config)
        
        # Adaptive learning state
        self.rate_limit_history = deque(maxlen=100)
        self.success_history = deque(maxlen=100)
        self.learning_rate = 0.1
        
    async def acquire_token(self, wait: bool = True) -> bool:
        """Acquire a token with adaptive rate limiting"""
        return await self.rate_limiter.acquire_token(wait)
    
    def record_rate_limit(self, timestamp: float = None):
        """Record when a rate limit was hit"""
        if timestamp is None:
            timestamp = time.time()
        
        self.rate_limiter.rate_limited_requests += 1
        self.rate_limiter.last_rate_limit_time = timestamp
        self.rate_limit_history.append(timestamp)
        
        # Adjust rate limiting parameters
        self._adapt_to_rate_limits()
    
    def record_success(self, timestamp: float = None):
        """Record when a request was successful"""
        if timestamp is None:
            timestamp = time.time()
        
        self.success_history.append(timestamp)
        
        # Adjust rate limiting parameters
        self._adapt_to_success()
    
    def _adapt_to_rate_limits(self):
        """Adapt rate limiting parameters when rate limits are hit"""
        # Reduce request rate when rate limits are hit
        current_rate = self.current_config.requests_per_minute
        new_rate = max(5, current_rate * (1 - self.learning_rate))
        
        if new_rate != current_rate:
            self.current_config.requests_per_minute = new_rate
            logger.info(f"Rate limit hit, reducing rate to {new_rate} requests/minute")
            
            # Recreate rate limiter with new config
            self.rate_limiter = TokenBucketRateLimiter(self.current_config)
    
    def _adapt_to_success(self):
        """Adapt rate limiting parameters when requests are successful"""
        # Gradually increase rate when requests are successful
        if len(self.success_history) >= 10:
            # Check if we've had consistent success
            recent_successes = [t for t in self.success_history if time.time() - t < 300]  # Last 5 minutes
            
            if len(recent_successes) >= 8:  # At least 8 successful requests in last 5 minutes
                current_rate = self.current_config.requests_per_minute
                new_rate = min(
                    self.base_config.requests_per_minute,
                    current_rate * (1 + self.learning_rate * 0.5)  # Slower increase
                )
                
                if new_rate != current_rate:
                    self.current_config.requests_per_minute = new_rate
                    logger.info(f"Consistent success, increasing rate to {new_rate} requests/minute")
                    
                    # Recreate rate limiter with new config
                    self.rate_limiter = TokenBucketRateLimiter(self.current_config)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current adaptive rate limiting statistics"""
        base_stats = self.rate_limiter.get_stats()
        base_stats["adaptive"] = {
            "base_config": {
                "requests_per_minute": self.base_config.requests_per_minute,
                "burst_limit": self.base_config.burst_limit
            },
            "current_config": {
                "requests_per_minute": self.current_config.requests_per_minute,
                "burst_limit": self.current_config.burst_limit
            },
            "learning": {
                "learning_rate": self.learning_rate,
                "rate_limit_history_count": len(self.rate_limit_history),
                "success_history_count": len(self.success_history)
            }
        }
        return base_stats


# Global rate limiter instance
_global_rate_limiter: Optional[AdaptiveRateLimiter] = None


def get_global_rate_limiter() -> AdaptiveRateLimiter:
    """Get the global rate limiter instance"""
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        # Create with default configuration
        config = RateLimitConfig()
        _global_rate_limiter = AdaptiveRateLimiter(config)
        logger.info("Global rate limiter initialized with default configuration")
    
    return _global_rate_limiter


def set_global_rate_limiter_config(config: RateLimitConfig):
    """Set the global rate limiter configuration"""
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        _global_rate_limiter = AdaptiveRateLimiter(config)
    else:
        _global_rate_limiter.base_config = config
        _global_rate_limiter.current_config = config
        _global_rate_limiter.rate_limiter = TokenBucketRateLimiter(config)
    
    logger.info(f"Global rate limiter configuration updated: {config}")


async def wait_for_claude_token():
    """Wait for a Claude API token to become available"""
    rate_limiter = get_global_rate_limiter()
    await rate_limiter.acquire_token(wait=True)


def record_claude_rate_limit():
    """Record when a Claude API rate limit was hit"""
    rate_limiter = get_global_rate_limiter()
    rate_limiter.record_rate_limit()


def record_claude_success():
    """Record when a Claude API request was successful"""
    rate_limiter = get_global_rate_limiter()
    rate_limiter.record_success()
