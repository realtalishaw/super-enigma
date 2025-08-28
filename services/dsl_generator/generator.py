"""
DSL Generator Service - Simplified wrapper around SimpleWorkflowGenerator
"""

import logging
from typing import Dict, Any, Optional
from .models import GenerationRequest, GenerationResponse
from .simple_generator import SimpleWorkflowGenerator

logger = logging.getLogger(__name__)


class DSLGeneratorService:
    """Simple wrapper for backward compatibility"""
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.generator = SimpleWorkflowGenerator(anthropic_api_key)
        self._catalog_cache = {}
    
    def set_global_cache(self, catalog_cache: Dict[str, Any]):
        """Set the catalog cache from the global cache service"""
        self._catalog_cache = catalog_cache
        self.generator.set_catalog_cache(catalog_cache)
    
    async def initialize(self):
        """Initialize the generator"""
        logger.info("DSL generator initialized")
    
    async def generate_workflow(self, request: GenerationRequest) -> GenerationResponse:
        """Generate a workflow from user request"""
        return await self.generator.generate_workflow(request)