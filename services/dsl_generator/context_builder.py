"""
Context Builder for DSL Generator

Handles building generation context from requests and catalog data,
including filtering and data extraction.
"""

import logging
import json
from typing import Dict, Any, List
from .models import GenerationRequest, GenerationContext, CatalogContext
from .catalog_manager import CatalogManager

logger = logging.getLogger(__name__)

def log_json_pretty(data: Any, prefix: str = "", max_length: int = 2000):
    """Helper function to log JSON data in a pretty format with length limits"""
    try:
        if isinstance(data, (dict, list)):
            json_str = json.dumps(data, indent=2, default=str)
            if len(json_str) > max_length:
                json_str = json_str[:max_length] + "... [TRUNCATED]"
            logger.info(f"{prefix}\n{json_str}")
        else:
            logger.info(f"{prefix}: {data}")
    except Exception as e:
        logger.error(f"Failed to log JSON data: {e}")
        logger.info(f"{prefix}: {str(data)[:500]}")

def log_function_entry(func_name: str, **kwargs):
    """Log function entry with parameters"""
    logger.info(f"🔵 ENTERING {func_name}")
    for key, value in kwargs.items():
        if isinstance(value, (dict, list)):
            log_json_pretty(value, f"  📥 {key}:")
        else:
            logger.info(f"  📥 {key}: {value}")

def log_function_exit(func_name: str, result: Any = None, success: bool = True):
    """Log function exit with result"""
    status = "✅" if success else "❌"
    logger.info(f"{status} EXITING {func_name}")
    if result is not None:
        if isinstance(result, (dict, list)):
            log_json_pretty(result, f"  📤 Result:")
        else:
            logger.info(f"  📤 Result: {result}")


class ContextBuilder:
    """
    Builds generation context from requests and catalog data.
    
    Responsibilities:
    - Building generation context
    - Filtering catalog by selected apps
    - Extracting catalog data for context
    - Managing context state
    """
    
    def __init__(self, catalog_manager: CatalogManager):
        """Initialize the context builder with a catalog manager"""
        self.catalog_manager = catalog_manager
    
    async def build_generation_context(self, request: GenerationRequest) -> GenerationContext:
        """Build the full context for generation"""
        log_function_entry("build_generation_context", request=request)
        
        try:
            # Get catalog data from cache or service
            logger.info("🔍 Getting catalog data from cache or service...")
            providers = await self.catalog_manager.get_catalog_data()
            log_json_pretty(list(providers.keys())[:10], "📋 Available providers (first 10):")
            
            # Build catalog context
            logger.info("🔧 Building catalog context...")
            catalog_context = CatalogContext(
                available_providers=list(providers.values()) if providers else [],
                available_triggers=self.catalog_manager.extract_triggers(providers),
                available_actions=self.catalog_manager.extract_actions(providers),
                provider_categories=self.catalog_manager.extract_categories(providers)
            )
            
            # Log catalog context for debugging
            logger.info(f"✅ Built catalog context with:")
            logger.info(f"  - {len(catalog_context.available_providers)} providers")
            logger.info(f"  - {len(catalog_context.available_triggers)} triggers")
            logger.info(f"  - {len(catalog_context.available_actions)} actions")
            logger.info(f"  - {len(catalog_context.provider_categories)} categories")
            
            # Log sample triggers and actions
            if catalog_context.available_triggers:
                log_json_pretty(catalog_context.available_triggers[:3], "📋 Sample triggers (first 3):")
            if catalog_context.available_actions:
                log_json_pretty(catalog_context.available_actions[:3], "📋 Sample actions (first 3):")
            
            # Debug: log sample data
            if catalog_context.available_actions:
                logger.debug(f"Sample action: {catalog_context.available_actions[0]}")
            if catalog_context.available_triggers:
                logger.debug(f"Sample trigger: {catalog_context.available_triggers[0]}")
            if catalog_context.available_providers:
                logger.debug(f"Sample provider: {catalog_context.available_providers[0]}")
            
            # Filter by selected apps if specified
            if request.selected_apps:
                logger.info(f"🎯 Filtering catalog by selected apps: {request.selected_apps}")
                catalog_context = self._filter_catalog_by_apps(
                    catalog_context, request.selected_apps
                )
                logger.info(f"✅ After filtering: {len(catalog_context.available_providers)} providers, {len(catalog_context.available_triggers)} triggers, {len(catalog_context.available_actions)} actions")
            else:
                logger.info("🎯 No selected apps filter - using full catalog")
            
            # Load schema definition
            logger.info("📋 Loading schema definition...")
            schema_definition = self._load_schema_definition()
            
            result = GenerationContext(
                request=request,
                catalog=catalog_context,
                schema_definition=schema_definition
            )
            
            log_function_exit("build_generation_context", result, success=True)
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to build generation context: {e}")
            # Return minimal context
            schema_definition = self._load_schema_definition()
            result = GenerationContext(
                request=request,
                catalog=CatalogContext(),
                schema_definition=schema_definition
            )
            log_function_exit("build_generation_context", result, success=False)
            return result
    
    def _filter_catalog_by_apps(
        self, 
        catalog_context: CatalogContext, 
        selected_apps: List[str]
    ) -> CatalogContext:
        """Filter catalog context to only include selected apps"""
        selected_apps_lower = [app.lower() for app in selected_apps]
        
        # Filter providers
        filtered_providers = [
            p for p in catalog_context.available_providers
            if p.get('slug', '').lower() in selected_apps_lower
        ]
        
        # Filter triggers and actions
        filtered_triggers = [
            t for t in catalog_context.available_triggers
            if t.get('toolkit_slug', '').lower() in selected_apps_lower
        ]
        
        filtered_actions = [
            a for a in catalog_context.available_actions
            if a.get('toolkit_slug', '').lower() in selected_apps_lower
        ]
        
        return CatalogContext(
            available_providers=filtered_providers,
            available_triggers=filtered_triggers,
            available_actions=filtered_actions,
            provider_categories=catalog_context.provider_categories
        )
    
    def _load_schema_definition(self) -> Dict[str, Any]:
        """Load the DSL schema definition"""
        try:
            import os
            schema_path = os.path.join(
                os.path.dirname(__file__), 
                "../../core/dsl/schema.json"
            )
            with open(schema_path, 'r') as f:
                import json
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load schema definition: {e}")
            # Return a minimal schema as fallback
            return {
                "title": "Weave Workflow DSL Schema",
                "description": "Workflow DSL schema for templates, executables, and DAGs"
            }
    
    def check_catalog_sufficiency(self, context: GenerationContext) -> Dict[str, Any]:
        """Check if the catalog has sufficient data to generate meaningful workflows"""
        return self.catalog_manager.check_catalog_sufficiency()
    
    def get_catalog_for_generation(self) -> Dict[str, Any]:
        """Get catalog data specifically formatted for generation prompts"""
        if not self.catalog_manager._catalog_cache:
            return {"error": "No catalog data available"}
        
        # Get validation summary
        validation_summary = self._get_catalog_validation_summary()
        
        # Get sample workflow data
        sample_data = self._get_sample_workflow_data()
        
        # Get catalog overview
        overview = self._get_catalog_overview()
        
        # Combine into a comprehensive generation context
        return {
            "validation": validation_summary,
            "samples": sample_data,
            "overview": overview,
            "generation_ready": validation_summary.get('valid_providers', 0) > 0,
            "recommended_providers": sample_data.get('valid_providers', [])[:5]
        }
    
    def _get_catalog_validation_summary(self) -> Dict[str, Any]:
        """Get a summary of catalog validation for generation context"""
        if not self.catalog_manager._catalog_cache:
            return {"error": "No catalog data available"}
        
        # Count valid providers (those with both triggers and actions)
        valid_providers = 0
        providers_with_triggers_only = 0
        providers_with_actions_only = 0
        providers_with_neither = 0
        
        for provider in self.catalog_manager._catalog_cache.values():
            triggers = provider.get('triggers', [])
            actions = provider.get('actions', [])
            
            if triggers and actions:
                valid_providers += 1
            elif triggers:
                providers_with_triggers_only += 1
            elif actions:
                providers_with_actions_only += 1
            else:
                providers_with_neither += 1
        
        # Get sample valid providers for generation
        sample_valid_providers = []
        for slug, provider in self.catalog_manager._catalog_cache.items():
            triggers = provider.get('triggers', [])
            actions = provider.get('actions', [])
            if triggers and actions:
                sample_valid_providers.append({
                    "slug": slug,
                    "name": provider.get('name', slug),
                    "sample_trigger": triggers[0].get('name', 'Unknown'),
                    "sample_action": actions[0].get('name', 'Unknown')
                })
                if len(sample_valid_providers) >= 5:  # Limit to 5 examples
                    break
        
        return {
            "total_providers": len(self.catalog_manager._catalog_cache),
            "valid_providers": valid_providers,
            "providers_with_triggers_only": providers_with_triggers_only,
            "providers_with_actions_only": providers_with_actions_only,
            "providers_with_neither": providers_with_neither,
            "sample_valid_providers": sample_valid_providers,
            "catalog_quality": "good" if valid_providers > len(self.catalog_manager._catalog_cache) * 0.5 else "poor"
        }
    
    def _get_sample_workflow_data(self) -> Dict[str, Any]:
        """Get sample workflow data for generation prompts"""
        if not self.catalog_manager._catalog_cache:
            return {"error": "No catalog data available"}
        
        # Find providers with both triggers and actions
        valid_providers = []
        for slug, provider in self.catalog_manager._catalog_cache.items():
            triggers = provider.get('triggers', [])
            actions = provider.get('actions', [])
            if triggers and actions:
                valid_providers.append({
                    "slug": slug,
                    "name": provider.get('name', slug),
                    "sample_trigger": triggers[0].get('name', 'Unknown'),
                    "sample_action": actions[0].get('name', 'Unknown'),
                    "triggers_count": len(triggers),
                    "actions_count": len(actions)
                })
        
        # Sort by number of available tools
        valid_providers.sort(key=lambda x: x['triggers_count'] + x['actions_count'], reverse=True)
        
        return {
            "valid_providers": valid_providers[:10],  # Top 10 providers
            "total_valid_providers": len(valid_providers),
            "sample_workflow_structure": {
                "trigger": valid_providers[0]['sample_trigger'] if valid_providers else "notification",
                "action": valid_providers[0]['sample_action'] if valid_providers else "notification"
            }
        }
    
    def _get_catalog_overview(self) -> Dict[str, Any]:
        """Get a high-level overview of the catalog for generation context"""
        if not self.catalog_manager._catalog_cache:
            return {"error": "No catalog data available"}
        
        # Count providers by category
        categories = {}
        for provider in self.catalog_manager._catalog_cache.values():
            category = provider.get('category', 'Unknown')
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        # Get top providers by tool count
        provider_tool_counts = []
        for slug, provider in self.catalog_manager._catalog_cache.items():
            total_tools = len(provider.get('triggers', [])) + len(provider.get('actions', []))
            provider_tool_counts.append({
                "slug": slug,
                "name": provider.get('name', slug),
                "total_tools": total_tools
            })
        
        # Sort by tool count and get top 10
        provider_tool_counts.sort(key=lambda x: x['total_tools'], reverse=True)
        top_providers = provider_tool_counts[:10]
        
        return {
            "total_providers": len(self.catalog_manager._catalog_cache),
            "categories": categories,
            "top_providers": top_providers,
            "catalog_ready": bool(self.catalog_manager._catalog_cache)
        }
