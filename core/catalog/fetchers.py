from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import asyncio
import logging
from datetime import datetime, timedelta

from .models import Provider, CatalogResponse, CatalogFilter

logger = logging.getLogger(__name__)

class CatalogFetcher(ABC):
    """Abstract base class for catalog data fetchers"""
    
    @abstractmethod
    async def fetch_providers(self, filter_params: Optional[CatalogFilter] = None) -> List[Provider]:
        """Fetch providers from the data source"""
        pass
    
    @abstractmethod
    async def fetch_provider(self, provider_id: str) -> Optional[Provider]:
        """Fetch a specific provider by ID"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the fetcher is healthy and accessible"""
        pass

class ComposioMCPFetcher(CatalogFetcher):
    """Fetcher for Composio MCP (Model Context Protocol) data"""
    
    def __init__(self, mcp_endpoint: str, api_key: Optional[str] = None):
        self.mcp_endpoint = mcp_endpoint
        self.api_key = api_key
        self.session = None
    
    async def fetch_providers(self, filter_params: Optional[CatalogFilter] = None) -> List[Provider]:
        """Fetch providers from Composio MCP endpoint"""
        try:
            # TODO: Implement actual MCP client connection
            # This is a placeholder implementation
            logger.info(f"Fetching providers from MCP endpoint: {self.mcp_endpoint}")
            
            # Simulate async operation
            await asyncio.sleep(0.1)
            
            # Return mock data for now
            return self._get_mock_providers()
            
        except Exception as e:
            logger.error(f"Error fetching providers from MCP: {e}")
            return []
    
    async def fetch_provider(self, provider_id: str) -> Optional[Provider]:
        """Fetch a specific provider from MCP"""
        try:
            providers = await self.fetch_providers()
            return next((p for p in providers if p.id == provider_id), None)
        except Exception as e:
            logger.error(f"Error fetching provider {provider_id} from MCP: {e}")
            return None
    
    async def health_check(self) -> bool:
        """Check MCP endpoint health"""
        try:
            # TODO: Implement actual health check
            return True
        except Exception as e:
            logger.error(f"MCP health check failed: {e}")
            return False
    
    def _get_mock_providers(self) -> List[Provider]:
        """Return mock provider data for development/testing"""
        from .models import (
            ProviderMetadata, ActionSpec, ParamSpec, ParamType,
            TriggerSpec, TriggerDelivery, Permission, Scope, ScopeLevel
        )
        
        # Mock Gmail provider
        gmail_params = [
            ParamSpec(
                name="query",
                type=ParamType.STRING,
                description="Search query for emails",
                required=True
            ),
            ParamSpec(
                name="max_results",
                type=ParamType.INTEGER,
                description="Maximum number of results",
                default=10,
                min_value=1,
                max_value=100
            )
        ]
        
        gmail_actions = [
            ActionSpec(
                name="search_emails",
                description="Search for emails in Gmail",
                parameters=gmail_params
            )
        ]
        
        gmail_triggers = [
            TriggerSpec(
                name="new_email",
                description="Triggered when a new email arrives",
                delivery=[TriggerDelivery.WEBHOOK]
            )
        ]
        
        gmail_provider = Provider(
            id="gmail",
            metadata=ProviderMetadata(
                name="Gmail",
                description="Google Gmail integration",
                website="https://gmail.com",
                category="communication",
                tags=["email", "google", "communication"]
            ),
            actions=gmail_actions,
            triggers=gmail_triggers,
            permissions=[
                Permission(
                    name="Gmail Access",
                    description="Access to Gmail account",
                    scopes=[
                        Scope(resource="gmail.readonly", level=ScopeLevel.READ),
                        Scope(resource="gmail.send", level=ScopeLevel.WRITE)
                    ]
                )
            ]
        )
        
        return [gmail_provider]

class ComposioSDKFetcher(CatalogFetcher):
    """Fetcher for Composio SDK data"""
    
    def __init__(self, sdk_config: Dict[str, Any]):
        self.sdk_config = sdk_config
        self.client = None
    
    async def fetch_providers(self, filter_params: Optional[CatalogFilter] = None) -> List[Provider]:
        """Fetch providers from Composio SDK"""
        try:
            # TODO: Implement actual SDK client
            logger.info("Fetching providers from Composio SDK")
            
            # Simulate async operation
            await asyncio.sleep(0.1)
            
            # Return mock data for now
            return self._get_mock_sdk_providers()
            
        except Exception as e:
            logger.error(f"Error fetching providers from SDK: {e}")
            return []
    
    async def fetch_provider(self, provider_id: str) -> Optional[Provider]:
        """Fetch a specific provider from SDK"""
        try:
            providers = await self.fetch_providers()
            return next((p for p in providers if p.id == provider_id), None)
        except Exception as e:
            logger.error(f"Error fetching provider {provider_id} from SDK: {e}")
            return None
    
    async def health_check(self) -> bool:
        """Check SDK health"""
        try:
            # TODO: Implement actual health check
            return True
        except Exception as e:
            logger.error(f"SDK health check failed: {e}")
            return False
    
    def _get_mock_sdk_providers(self) -> List[Provider]:
        """Return mock SDK provider data"""
        from .models import (
            ProviderMetadata, ActionSpec, ParamSpec, ParamType,
            TriggerSpec, TriggerDelivery, Permission, Scope, ScopeLevel
        )
        
        # Mock Slack provider
        slack_params = [
            ParamSpec(
                name="channel",
                type=ParamType.STRING,
                description="Slack channel to post to",
                required=True
            ),
            ParamSpec(
                name="message",
                type=ParamType.STRING,
                description="Message to post",
                required=True
            )
        ]
        
        slack_actions = [
            ActionSpec(
                name="post_message",
                description="Post a message to a Slack channel",
                parameters=slack_params
            )
        ]
        
        slack_triggers = [
            TriggerSpec(
                name="message_received",
                description="Triggered when a message is received",
                delivery=[TriggerDelivery.WEBHOOK]
            )
        ]
        
        slack_provider = Provider(
            id="slack",
            metadata=ProviderMetadata(
                name="Slack",
                description="Slack workspace integration",
                website="https://slack.com",
                category="communication",
                tags=["chat", "team", "communication"]
            ),
            actions=slack_actions,
            triggers=slack_triggers,
            permissions=[
                Permission(
                    name="Slack Access",
                    description="Access to Slack workspace",
                    scopes=[
                        Scope(resource="channels:read", level=ScopeLevel.READ),
                        Scope(resource="chat:write", level=ScopeLevel.WRITE)
                    ]
                )
            ]
        )
        
        return [slack_provider]

class CompositeFetcher(CatalogFetcher):
    """Composite fetcher that combines multiple data sources"""
    
    def __init__(self, fetchers: List[CatalogFetcher]):
        self.fetchers = fetchers
    
    async def fetch_providers(self, filter_params: Optional[CatalogFilter] = None) -> List[Provider]:
        """Fetch providers from all fetchers and merge results"""
        all_providers = []
        
        for fetcher in self.fetchers:
            try:
                providers = await fetcher.fetch_providers(filter_params)
                all_providers.extend(providers)
            except Exception as e:
                logger.error(f"Error with fetcher {fetcher.__class__.__name__}: {e}")
                continue
        
        # Remove duplicates based on provider ID
        unique_providers = {}
        for provider in all_providers:
            if provider.id not in unique_providers:
                unique_providers[provider.id] = provider
            else:
                # Keep the most recently updated version
                if provider.updated_at > unique_providers[provider.id].updated_at:
                    unique_providers[provider.id] = provider
        
        return list(unique_providers.values())
    
    async def fetch_provider(self, provider_id: str) -> Optional[Provider]:
        """Fetch a specific provider from any available fetcher"""
        for fetcher in self.fetchers:
            try:
                provider = await fetcher.fetch_provider(provider_id)
                if provider:
                    return provider
            except Exception as e:
                logger.error(f"Error with fetcher {fetcher.__class__.__name__}: {e}")
                continue
        
        return None
    
    async def health_check(self) -> bool:
        """Check health of all fetchers"""
        health_checks = await asyncio.gather(
            *[fetcher.health_check() for fetcher in self.fetchers],
            return_exceptions=True
        )
        
        healthy_count = sum(1 for result in health_checks if result is True)
        return healthy_count > 0  # At least one fetcher must be healthy
