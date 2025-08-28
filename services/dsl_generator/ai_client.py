"""
AI Client for DSL Generator

Handles Claude API calls and manages the AI interaction layer
for workflow generation.
"""

import logging
import httpx
from typing import Optional
from core.config import settings

logger = logging.getLogger(__name__)


class AIClient:
    """
    Client for interacting with Claude AI API.
    
    Responsibilities:
    - Making Claude API calls
    - Managing API authentication
    - Handling API responses and errors
    - Managing request timeouts and retries
    """
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        """Initialize the AI client"""
        self.anthropic_api_key = anthropic_api_key or settings.anthropic_api_key
        self.claude_model = "claude-3-5-sonnet-20241022"  # Latest Claude model
        self.base_url = "https://api.anthropic.com/v1/messages"
        
        if not self.anthropic_api_key:
            logger.warning("No Anthropic API key provided - AI client will not function")
    
    async def generate_workflow(self, prompt: str) -> str:
        """Call the Claude API to generate the workflow"""
        if not self.anthropic_api_key:
            raise ValueError("Anthropic API key is required for Claude access")
        
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
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                return result["content"][0]["text"]
                
        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            raise RuntimeError(f"Failed to call Claude API: {e}")
    
    def is_configured(self) -> bool:
        """Check if the AI client is properly configured"""
        return bool(self.anthropic_api_key)
    
    def get_model_info(self) -> dict:
        """Get information about the current model configuration"""
        return {
            "model": self.claude_model,
            "base_url": self.base_url,
            "configured": self.is_configured(),
            "api_key_present": bool(self.anthropic_api_key)
        }
    
    def update_api_key(self, new_api_key: str):
        """Update the API key"""
        self.anthropic_api_key = new_api_key
        logger.info("API key updated")
    
    def update_model(self, new_model: str):
        """Update the Claude model"""
        self.claude_model = new_model
        logger.info(f"Claude model updated to: {new_model}")
