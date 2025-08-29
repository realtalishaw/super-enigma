# Rate Limiting System for Claude API

This document describes the rate limiting system implemented to prevent overwhelming the Claude API and ensure reliable workflow generation.

## Overview

The rate limiting system consists of two main components:

1. **Global Rate Limiter** (`rate_limiter.py`) - Centralized rate limiting for all Claude API calls
2. **Enhanced AI Client** (`ai_client.py`) - AI client with integrated rate limiting and retry logic

## Features

### 🚦 **Token Bucket Rate Limiting**
- Configurable requests per minute (default: 20)
- Burst limit support (default: 5 concurrent requests)
- Sliding window implementation for accurate rate control

### 🔄 **Adaptive Rate Limiting**
- Automatically adjusts limits based on API response patterns
- Reduces rate when 429 errors occur
- Gradually increases rate during successful periods
- Learning rate: 10% adjustment per rate limit hit

### ⚡ **Exponential Backoff with Jitter**
- Intelligent retry logic using the `tenacity` library
- Exponential backoff: base_delay × 2^attempt
- Jitter (±25%) to prevent thundering herd
- Maximum 5 retry attempts

### 📊 **Comprehensive Monitoring**
- Real-time rate limiting statistics
- Request success/failure tracking
- Adaptive learning metrics
- API endpoints for monitoring and configuration

## Configuration

### Environment Variables

```bash
# Rate limiting configuration
CLAUDE_RATE_LIMIT_DELAY=2.0          # Base delay between requests (seconds)
MAX_RATE_LIMIT_DELAY=30.0            # Maximum delay between requests (seconds)
```

### Programmatic Configuration

```python
from services.dsl_generator.rate_limiter import RateLimitConfig, set_global_rate_limiter_config

# Configure rate limiting
config = RateLimitConfig(
    requests_per_minute=15,    # 15 requests per minute
    burst_limit=3,             # Allow burst of 3 requests
    base_delay=3.0,           # 3 seconds base delay
    max_delay=45.0,           # 45 seconds maximum delay
    jitter_factor=0.3         # ±30% random variation
)

set_global_rate_limiter_config(config)
```

## Usage

### Basic Usage

```python
from services.dsl_generator.ai_client import AIClient

# Create AI client (automatically uses global rate limiter)
client = AIClient(anthropic_api_key="your_api_key")

# Generate workflow (rate limiting is automatic)
try:
    workflow = await client.generate_workflow("Your prompt here")
    print(f"Generated workflow: {workflow}")
except Exception as e:
    print(f"Generation failed: {e}")
```

### Advanced Usage

```python
from services.dsl_generator.rate_limiter import get_global_rate_limiter

# Get rate limiter instance
rate_limiter = get_global_rate_limiter()

# Wait for token before making request
await rate_limiter.acquire_token()

# Make your request here
# ...

# Record success/failure for adaptive learning
rate_limiter.record_success()  # or record_rate_limit()
```

### Fallback Generation

```python
# Use fallback generation for better success rate
try:
    workflow = await client.generate_workflow_with_fallback("Your prompt")
except Exception as e:
    print(f"Both attempts failed: {e}")
```

## Monitoring

### API Endpoints

```bash
# Get current rate limiting status
GET /api/system/rate-limiting/status

# Configure rate limiting parameters
POST /api/system/rate-limiting/configure
{
    "requests_per_minute": 15,
    "burst_limit": 3,
    "base_delay": 3.0,
    "max_delay": 45.0
}

# Get AI client status
GET /api/system/ai-client/status
```

### Programmatic Monitoring

```python
from services.dsl_generator.rate_limiter import get_global_rate_limiter

rate_limiter = get_global_rate_limiter()
stats = rate_limiter.get_stats()

print(f"Available tokens: {stats['current_state']['available_tokens']}")
print(f"Total requests: {stats['current_state']['total_requests']}")
print(f"Rate limited requests: {stats['current_state']['rate_limited_requests']}")
print(f"Current rate: {stats['current_state']['requests_per_minute']} requests/minute")
```

## Testing

Run the test script to verify rate limiting functionality:

```bash
cd services/dsl_generator
python test_rate_limiting.py
```

This will test:
- Basic token acquisition
- Concurrent request handling
- Adaptive rate limiting
- Configuration updates

## Troubleshooting

### Common Issues

1. **Rate limit errors still occurring**
   - Check if multiple processes are using the API
   - Verify rate limiting configuration
   - Monitor rate limiting statistics

2. **Slow response times**
   - Check current rate limiting settings
   - Monitor token availability
   - Consider increasing `requests_per_minute`

3. **Adaptive learning not working**
   - Ensure `record_success()` and `record_rate_limit()` are called
   - Check learning rate configuration
   - Monitor adaptive metrics

### Debug Mode

Enable debug logging to see detailed rate limiting information:

```python
import logging
logging.getLogger('services.dsl_generator.rate_limiter').setLevel(logging.DEBUG)
logging.getLogger('services.dsl_generator.ai_client').setLevel(logging.DEBUG)
```

## Performance Impact

- **Latency**: Adds 0-3 seconds per request (depending on rate limiting)
- **Throughput**: Reduces from unlimited to configurable requests per minute
- **Reliability**: Significantly improves success rate by preventing 429 errors
- **Scalability**: Supports concurrent requests with burst limits

## Best Practices

1. **Start Conservative**: Begin with lower request rates and increase gradually
2. **Monitor Metrics**: Regularly check rate limiting statistics
3. **Use Fallbacks**: Implement fallback generation for critical workflows
4. **Adapt to Patterns**: Let the adaptive system learn from your usage patterns
5. **Test Thoroughly**: Verify rate limiting behavior in your environment

## Migration from Old System

The new rate limiting system is backward compatible. Existing code will automatically benefit from:

- Centralized rate limiting
- Automatic retry logic
- Adaptive learning
- Better error handling

No code changes are required for basic functionality.
