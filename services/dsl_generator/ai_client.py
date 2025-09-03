"""
AI Client for DSL Generator

Handles Claude API calls and manages the AI interaction layer
for workflow generation.
"""

import asyncio
import random
import time
import uuid
import logging
from typing import Optional, Dict, Any
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    before_sleep_log
)
import httpx
from httpx import HTTPStatusError
from core.config import settings
from core.logging_config import get_logger, get_llm_logger
from .rate_limiter import wait_for_claude_token, record_claude_rate_limit, record_claude_success

logger = get_logger(__name__)
llm_logger = get_llm_logger(__name__)


class RateLimitExceededError(Exception):
    """Custom exception for rate limit exceeded errors"""
    pass


class AIClient:
    """
    Client for interacting with Claude AI API.
    
    Responsibilities:
    - Making Claude API calls
    - Managing API authentication
    - Handling API responses and errors
    - Managing request timeouts and retries
    - Implementing rate limiting with exponential backoff
    """
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        """Initialize the AI client"""
        self.anthropic_api_key = anthropic_api_key or settings.anthropic_api_key
        self.claude_model = "claude-3-5-sonnet-20241022"  # Latest Claude model
        self.base_url = "https://api.anthropic.com/v1/messages"
        
        # Rate limiting configuration
        self.base_delay = getattr(settings, 'claude_rate_limit_delay', 2.0)
        self.max_delay = getattr(settings, 'max_rate_limit_delay', 30.0)
        self.max_retries = 5
        
        # Rate limiting state
        self.last_request_time = 0
        self.request_count = 0
        self.rate_limit_window = 60  # 1 minute window
        
        if not self.anthropic_api_key:
            logger.warning("No Anthropic API key provided - AI client will not function")
    
    def _should_retry_exception(self, exception: Exception) -> bool:
        """Determine if an exception should trigger a retry"""
        if isinstance(exception, HTTPStatusError):
            # Retry on 429 (rate limit), 500 (server error), 502, 503, 504 (gateway errors)
            return exception.response.status_code in [429, 500, 502, 503, 504]
        return False
    
    def _get_retry_wait_time(self, attempt: int, base_delay: float = None) -> float:
        """Calculate exponential backoff wait time with jitter"""
        if base_delay is None:
            base_delay = self.base_delay
        
        # Exponential backoff: base_delay * 2^attempt
        wait_time = min(base_delay * (2 ** attempt), self.max_delay)
        
        # Add jitter (±25% random variation) to prevent thundering herd
        jitter = random.uniform(0.75, 1.25)
        wait_time *= jitter
        
        return wait_time
    
    async def _wait_for_rate_limit(self, attempt: int):
        """Wait before retrying due to rate limiting"""
        wait_time = self._get_retry_wait_time(attempt)
        logger.info(f"Rate limit hit, waiting {wait_time:.2f}s before retry (attempt {attempt + 1})")
        await asyncio.sleep(wait_time)
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.INFO)
    )
    async def generate_workflow(self, prompt: str) -> str:
        """Call the Claude API to generate the workflow with retry logic"""
        if not self.anthropic_api_key:
            raise ValueError("Anthropic API key is required for Claude access")
        
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())[:8]
        
        # Log LLM request
        llm_logger.log_llm_request(
            model=self.claude_model,
            prompt=prompt,
            request_id=request_id
        )
        
        # Wait for rate limiter token before making request
        await wait_for_claude_token()
        
        # Check local rate limiting
        current_time = time.time()
        if current_time - self.last_request_time < 1.0:  # Minimum 1 second between requests
            wait_time = 1.0 - (current_time - self.last_request_time)
            logger.debug(f"Local rate limiting: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": self.claude_model,
            "max_tokens": 4000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        try:
            # Update request tracking
            self.last_request_time = time.time()
            self.request_count += 1
            
            # Record start time for response timing
            start_time = time.time()
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )
                
                # Handle rate limiting specifically
                if response.status_code == 429:
                    # Record rate limit for adaptive learning
                    record_claude_rate_limit()
                    
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        wait_time = float(retry_after)
                        logger.warning(f"Rate limit exceeded, waiting {wait_time}s as specified by Retry-After header")
                        await asyncio.sleep(wait_time)
                    else:
                        # Use exponential backoff if no Retry-After header
                        wait_time = self._get_retry_wait_time(0)
                        logger.warning(f"Rate limit exceeded, waiting {wait_time}s with exponential backoff")
                        await asyncio.sleep(wait_time)
                    
                    # Raise exception to trigger retry
                    raise HTTPStatusError("Rate limit exceeded", request=response.request, response=response)
                
                response.raise_for_status()
                
                # Record successful request for adaptive learning
                record_claude_success()
                
                # Calculate response time
                response_time_ms = (time.time() - start_time) * 1000
                
                result = response.json()
                response_text = result["content"][0]["text"]
                
                # Log LLM response
                llm_logger.log_llm_response(
                    model=self.claude_model,
                    response=response_text,
                    request_id=request_id,
                    duration_ms=response_time_ms
                )
                
                return response_text
                
        except HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning(f"Rate limit exceeded (429): {e}")
                raise RateLimitExceededError(f"Rate limit exceeded: {e}")
            else:
                logger.error(f"HTTP error from Claude API: {e}")
                raise RuntimeError(f"HTTP error from Claude API: {e}")
        except httpx.ConnectError as e:
            logger.error(f"Connection error to Claude API: {e}")
            raise RuntimeError(f"Connection error to Claude API: {e}")
        except httpx.TimeoutException as e:
            logger.error(f"Timeout error to Claude API: {e}")
            raise RuntimeError(f"Timeout error to Claude API: {e}")
        except Exception as e:
            # Log LLM error
            llm_logger.log_llm_error(
                model=self.claude_model,
                error=str(e),
                request_id=request_id
            )
            logger.error(f"Unexpected error calling Claude API: {e}")
            raise RuntimeError(f"Failed to call Claude API: {e}")
    
    async def generate_workflow_with_fallback(self, prompt: str) -> str:
        """Generate workflow with fallback to simpler prompts if rate limited"""
        try:
            return await self.generate_workflow(prompt)
        except RateLimitExceededError:
            logger.warning("Rate limit exceeded, trying with simplified prompt")
            # Try with a simplified prompt that might be more likely to succeed
            simplified_prompt = self._simplify_prompt(prompt)
            return await self.generate_workflow(simplified_prompt)
    
    def _simplify_prompt(self, prompt: str) -> str:
        """Simplify the prompt to reduce token usage and increase success rate"""
        # Basic prompt simplification - you can enhance this based on your needs
        lines = prompt.split('\n')
        if len(lines) > 3:
            # Keep only the first few lines to reduce complexity
            simplified = '\n'.join(lines[:3]) + "\n\nPlease generate a simple workflow for this request."
        else:
            simplified = prompt + "\n\nPlease generate a simple workflow for this request."
        return simplified
    
    def is_configured(self) -> bool:
        """Check if the AI client is properly configured"""
        return bool(self.anthropic_api_key)
    
    def get_model_info(self) -> dict:
        """Get information about the current model configuration"""
        return {
            "model": self.claude_model,
            "base_url": self.base_url,
            "configured": self.is_configured(),
            "api_key_present": bool(self.anthropic_api_key),
            "rate_limiting": {
                "base_delay": self.base_delay,
                "max_delay": self.max_delay,
                "max_retries": self.max_retries
            }
        }
    
    def update_api_key(self, new_api_key: str):
        """Update the API key"""
        self.anthropic_api_key = new_api_key
        logger.info("API key updated")
    
    def update_model(self, new_model: str):
        """Update the Claude model"""
        self.claude_model = new_model
        logger.info(f"Claude model updated to: {new_model}")
    
    def update_rate_limiting(self, base_delay: Optional[float] = None, max_delay: Optional[float] = None, max_retries: Optional[int] = None):
        """Update rate limiting configuration"""
        if base_delay is not None:
            self.base_delay = base_delay
        if max_delay is not None:
            self.max_delay = max_delay
        if max_retries is not None:
            self.max_retries = max_retries
        
        logger.info(f"Rate limiting updated: base_delay={self.base_delay}s, max_delay={self.max_delay}s, max_retries={self.max_retries}")
    
    def get_rate_limiting_stats(self) -> Dict[str, Any]:
        """Get current rate limiting statistics"""
        current_time = time.time()
        return {
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "max_retries": self.max_retries,
            "last_request_time": self.last_request_time,
            "request_count": self.request_count,
            "time_since_last_request": current_time - self.last_request_time if self.last_request_time > 0 else None,
            "requests_per_minute": self.request_count / max(1, (current_time - (current_time - self.rate_limit_window)) / 60)
        }
