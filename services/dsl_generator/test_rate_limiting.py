#!/usr/bin/env python3
"""
Test script for rate limiting functionality

This script tests the rate limiting and retry logic to ensure it's working correctly.
Run this to verify that the rate limiting prevents overwhelming the Claude API.
"""

import asyncio
import time
import logging
from typing import List
from rate_limiter import get_global_rate_limiter, RateLimitConfig
from ai_client import AIClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_rate_limiter():
    """Test the rate limiter functionality"""
    logger.info("Testing rate limiter...")
    
    # Get the global rate limiter
    rate_limiter = get_global_rate_limiter()
    
    # Test basic token acquisition
    logger.info("Testing basic token acquisition...")
    start_time = time.time()
    
    for i in range(10):
        await rate_limiter.acquire_token()
        logger.info(f"Acquired token {i+1}/10")
    
    elapsed = time.time() - start_time
    logger.info(f"Acquired 10 tokens in {elapsed:.2f}s")
    
    # Test rate limiting stats
    stats = rate_limiter.get_stats()
    logger.info(f"Rate limiter stats: {stats}")
    
    return True


async def test_ai_client_rate_limiting():
    """Test the AI client with rate limiting"""
    logger.info("Testing AI client rate limiting...")
    
    # Create AI client (without API key for testing)
    client = AIClient(anthropic_api_key="test_key")
    
    # Test rate limiting configuration
    logger.info(f"AI client rate limiting config: {client.get_rate_limiting_stats()}")
    
    # Test rate limiting update
    client.update_rate_limiting(base_delay=1.0, max_delay=10.0)
    logger.info(f"Updated AI client rate limiting config: {client.get_rate_limiting_stats()}")
    
    return True


async def test_concurrent_requests():
    """Test concurrent requests with rate limiting"""
    logger.info("Testing concurrent requests with rate limiting...")
    
    rate_limiter = get_global_rate_limiter()
    
    async def make_request(request_id: int):
        """Simulate making a request"""
        await rate_limiter.acquire_token()
        logger.info(f"Request {request_id} acquired token")
        # Simulate some processing time
        await asyncio.sleep(0.1)
        logger.info(f"Request {request_id} completed")
        return request_id
    
    # Create multiple concurrent requests
    tasks = [make_request(i) for i in range(15)]
    
    start_time = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time
    
    logger.info(f"Completed {len(results)} concurrent requests in {elapsed:.2f}s")
    
    # Check stats
    stats = rate_limiter.get_stats()
    logger.info(f"Final rate limiter stats: {stats}")
    
    return results


async def test_adaptive_rate_limiting():
    """Test adaptive rate limiting behavior"""
    logger.info("Testing adaptive rate limiting...")
    
    rate_limiter = get_global_rate_limiter()
    
    # Simulate some successful requests
    for i in range(5):
        rate_limiter.record_success()
        await asyncio.sleep(0.1)
    
    logger.info("Recorded 5 successful requests")
    
    # Simulate rate limit hits
    for i in range(3):
        rate_limiter.record_rate_limit()
        await asyncio.sleep(0.1)
    
    logger.info("Recorded 3 rate limit hits")
    
    # Check how the rate limiter adapted
    stats = rate_limiter.get_stats()
    logger.info(f"Adaptive rate limiter stats: {stats}")
    
    return True


async def test_rate_limiter_configuration():
    """Test rate limiter configuration updates"""
    logger.info("Testing rate limiter configuration...")
    
    from rate_limiter import set_global_rate_limiter_config
    
    # Test with different configuration
    config = RateLimitConfig(
        requests_per_minute=10,
        burst_limit=3,
        base_delay=1.0,
        max_delay=15.0
    )
    
    set_global_rate_limiter_config(config)
    logger.info("Updated global rate limiter configuration")
    
    # Get the updated rate limiter
    rate_limiter = get_global_rate_limiter()
    stats = rate_limiter.get_stats()
    logger.info(f"Updated rate limiter stats: {stats}")
    
    return True


async def main():
    """Run all tests"""
    logger.info("Starting rate limiting tests...")
    
    try:
        # Test 1: Basic rate limiter functionality
        await test_rate_limiter()
        
        # Test 2: AI client rate limiting
        await test_ai_client_rate_limiting()
        
        # Test 3: Concurrent requests
        await test_concurrent_requests()
        
        # Test 4: Adaptive rate limiting
        await test_adaptive_rate_limiting()
        
        # Test 5: Configuration updates
        await test_rate_limiter_configuration()
        
        logger.info("All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
