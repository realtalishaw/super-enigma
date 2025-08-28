import httpx
from typing import List, Dict, Any, Optional
import os

class UIClient:
    """Thin HTTP client to call backend APIs"""
    
    def __init__(self, api_base: str = "http://localhost:8000"):
        self.api_base = api_base
        self.client = httpx.AsyncClient()
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def generate_suggestions(self, prompt: str, integration_ids: List[str]) -> List[Dict[str, Any]]:
        """Generate workflow suggestions"""
        payload = {
            "prompt": prompt,
            "integration_ids": integration_ids
        }
        
        response = await self.client.post(f"{self.api_base}/api/suggestions:generate", json=payload)
        if response.status_code == 200:
            return response.json().get("suggestions", [])
        return []
    
    async def get_integrations(self) -> List[Dict[str, Any]]:
        """Get available integrations"""
        response = await self.client.get(f"{self.api_base}/api/integrations")
        if response.status_code == 200:
            return response.json().get("integrations", [])
        return []
    
    async def get_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user preferences for a specific user"""
        response = await self.client.get(f"{self.api_base}/api/preferences/{user_id}")
        if response.status_code == 200:
            return response.json()
        return {}
    
    async def get_auth_session(self) -> Optional[Dict[str, Any]]:
        """Get current auth session"""
        response = await self.client.get(f"{self.api_base}/api/auth/session")
        if response.status_code == 200:
            return response.json()
        return None
