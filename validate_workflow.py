#!/usr/bin/env python3
"""
Simple convenience script to validate and lint workflow JSON files

Usage:
    python validate_workflow.py <file.json>
    python validate_workflow.py --help
"""

import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, Any

# Import the validator functions
from core.validator import validate, lint, Stage, LintContext
from core.validator.json_output import validation_to_json, lint_to_json, comprehensive_to_dict


class HTTPCatalogAdapter:
    """Catalog adapter that makes HTTP requests to the running API server"""
    
    def __init__(self, api_url: str, session):
        self.api_url = api_url
        self.session = session
        self._catalog_cache = None
    
    async def get_provider_by_slug(self, slug: str):
        """Get provider by slug via HTTP API"""
        try:
            async with self.session.get(f"{self.api_url}/catalog/providers/{slug}", timeout=10) as response:
                if response.status == 200:
                    provider_data = await response.json()
                    # The provider data has tools.actions and tools.triggers
                    if provider_data.get("tools"):
                        return {
                            "metadata": {"slug": slug},
                            "actions": provider_data["tools"].get("actions", []),
                            "triggers": provider_data["tools"].get("triggers", [])
                        }
                return None
        except Exception as e:
            print(f"Error fetching provider {slug}: {e}")
            return None
    
    async def get_tool_by_slug(self, action_name: str, toolkit_slug: str):
        """Get tool by slug via HTTP API"""
        provider = await self.get_provider_by_slug(toolkit_slug)
        if not provider:
            return None
        
        # Look for the action in the provider's actions
        actions = provider.get("actions", [])
        for action in actions:
            if action.get("slug") == action_name:
                return action
        
        # Also check triggers
        triggers = provider.get("triggers", [])
        for trigger in triggers:
            if trigger.get("slug") == action_name:
                return trigger
        
        return None
    
    async def get_catalog(self):
        """Get full catalog data via HTTP API"""
        # For now, return empty providers since we fetch individually
        return {"providers": {}}


class MockConnections:
    """Mock connections for CLI usage when real connections are not available"""
    
    async def get_connection(self, connection_id: str):
        # Mock connection data
        return {
            "connection_id": connection_id,
            "scopes": ["read", "write"]
        }


async def get_real_catalog_context():
    """Get real catalog context from Redis cache via HTTP API"""
    try:
        import aiohttp
        
        # Try to connect to the running API server
        api_url = "http://localhost:8001"
        
        async with aiohttp.ClientSession() as session:
            # Check if the API server is running
            try:
                async with session.get(f"{api_url}/health", timeout=5) as response:
                    if response.status != 200:
                        raise Exception(f"API server health check failed: {response.status}")
            except Exception as e:
                raise Exception(f"Cannot connect to API server at {api_url}: {e}")
            
            # Get cache status
            async with session.get(f"{api_url}/cache/status", timeout=10) as response:
                if response.status != 200:
                    raise Exception(f"Cache status check failed: {response.status}")
                
                cache_status = await response.json()
                
                if not cache_status.get("cache", {}).get("has_cached_data"):
                    raise Exception("Cache has no data")
                
                provider_count = cache_status["cache"]["provider_count"]
                print(f"🔗 Connected to API server at {api_url}")
                print(f"📚 Cache has {provider_count} providers loaded")
            
            # Get catalog data
            async with session.get(f"{api_url}/cache/info", timeout=30) as response:
                if response.status != 200:
                    raise Exception(f"Failed to get catalog data: {response.status}")
                
                catalog_info = await response.json()
                
                if catalog_info.get("status") != "success":
                    raise Exception(f"Failed to get catalog data: {catalog_info.get('message', 'Unknown error')}")
                
                # Create a catalog adapter that makes HTTP requests
                catalog_adapter = HTTPCatalogAdapter(api_url, session)
                
                return LintContext(
                    catalog=catalog_adapter,
                    connections=MockConnections()
                )
                
    except ImportError:
        print("❌ aiohttp not available - install with: pip install aiohttp")
        raise Exception("aiohttp required for HTTP catalog access")
    except Exception as e:
        print(f"❌ Error accessing catalog via HTTP: {e}")
        print("💡 Make sure your API server is running on port 8001")
        print("💡 Start with: python start_both.py")
        raise Exception(f"HTTP catalog access failed: {e}")


async def validate_workflow(file_path: str):
    """Validate and lint a workflow JSON file"""
    try:
        # Load the JSON file
        print(f"🚀 Loading file: {file_path}")
        with open(file_path, 'r') as f:
            doc = json.load(f)
        
        # Determine the stage
        schema_type = doc.get("schema_type", "").lower()
        if schema_type == "template":
            stage = Stage.TEMPLATE
        elif schema_type == "executable":
            stage = Stage.EXECUTABLE
        elif schema_type == "dag":
            stage = Stage.DAG
        else:
            print(f"⚠️  Warning: Unknown schema_type '{schema_type}', defaulting to TEMPLATE")
            stage = Stage.TEMPLATE
        
        # Print summary
        print(f"📄 Processing: {doc.get('workflow', {}).get('name', 'Unnamed Workflow')}")
        print(f"🏷️  Stage: {stage.value}")
        print(f"📊 Schema Type: {doc.get('schema_type', 'Unknown')}")
        
        if "workflow" in doc:
            workflow = doc["workflow"]
            if "triggers" in workflow:
                print(f"🔔 Triggers: {len(workflow['triggers'])}")
            if "actions" in workflow:
                print(f"⚡ Actions: {len(workflow['actions'])}")
        
        print("-" * 50)
        
        # Run validation
        print("🔍 Running validation...")
        validation_result = await validate(stage, doc)
        validation_json = validation_to_json(validation_result, pretty=True)
        
        # Run linting with proper session management
        print("🧹 Running linting...")
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                context = await get_real_catalog_context_with_session(session)
                lint_result = await lint(stage, doc, context)
        except Exception as e:
            print(f"❌ Linting failed: {e}")
            # Create a minimal context for basic validation
            from core.validator.models import LintContext
            context = LintContext(
                catalog=None,
                connections=None
            )
            lint_result = await lint(stage, doc, context)
        
        lint_json = lint_to_json(lint_result, pretty=True)
        
        # Get comprehensive report
        comprehensive = comprehensive_to_dict(validation_result, lint_result)
        comprehensive_json = json.dumps(comprehensive, indent=2, default=str)
        
        # Print results
        print("\n📋 VALIDATION RESULTS:")
        print(validation_json)
        
        print("\n📋 LINTING RESULTS:")
        print(lint_json)
        
        print("\n📋 COMPREHENSIVE SUMMARY:")
        print(f"✅ Workflow Valid: {comprehensive['overall_summary']['workflow_valid']}")
        print(f"🚨 Has Lint Errors: {comprehensive['overall_summary']['has_lint_errors']}")
        print(f"⚠️  Has Lint Warnings: {comprehensive['overall_summary']['has_lint_warnings']}")
        print(f"🚀 Ready for Execution: {comprehensive['overall_summary']['ready_for_execution']}")
        
        # Print specific findings summary
        if lint_result.errors:
            print(f"\n🚨 LINTING ERRORS ({len(lint_result.errors)}):")
            for error in lint_result.errors:
                print(f"  • {error.code}: {error.message}")
                if error.hint:
                    print(f"    💡 Hint: {error.hint}")
        
        if lint_result.warnings:
            print(f"\n⚠️  LINTING WARNINGS ({len(lint_result.warnings)}):")
            for warning in lint_result.warnings:
                print(f"  • {warning.code}: {warning.message}")
                if warning.hint:
                    print(f"    💡 Hint: {warning.hint}")
        
        return comprehensive
        
    except FileNotFoundError:
        print(f"❌ Error: File '{file_path}' not found")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in '{file_path}': {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


async def get_real_catalog_context_with_session(session):
    """Get real catalog context using an existing aiohttp session"""
    try:
        # Try to connect to the running API server
        api_url = "http://localhost:8001"
        
        # Check if the API server is running
        try:
            async with session.get(f"{api_url}/health", timeout=5) as response:
                if response.status != 200:
                    raise Exception(f"API server health check failed: {response.status}")
        except Exception as e:
            raise Exception(f"Cannot connect to API server at {api_url}: {e}")
        
        # Get cache status
        async with session.get(f"{api_url}/cache/status", timeout=10) as response:
            if response.status != 200:
                raise Exception(f"Cache status check failed: {response.status}")
            
            cache_status = await response.json()
            
            if not cache_status.get("cache", {}).get("has_cached_data"):
                raise Exception("Cache has no data")
            
            provider_count = cache_status["cache"]["provider_count"]
            print(f"🔗 Connected to API server at {api_url}")
            print(f"📚 Cache has {provider_count} providers loaded")
        
        # Get catalog data
        async with session.get(f"{api_url}/cache/info", timeout=30) as response:
            if response.status != 200:
                raise Exception(f"Failed to get catalog data: {response.status}")
            
            catalog_info = await response.json()
            
            if catalog_info.get("status") != "success":
                raise Exception(f"Failed to get catalog data: {catalog_info.get('message', 'Unknown error')}")
            
            # Create a catalog adapter that makes HTTP requests
            catalog_adapter = HTTPCatalogAdapter(api_url, session)
            
            return LintContext(
                catalog=catalog_adapter,
                connections=MockConnections()
            )
            
    except Exception as e:
        print(f"❌ Error accessing catalog via HTTP: {e}")
        print("💡 Make sure your API server is running on port 8001")
        print("💡 Start with: python start_both.py")
        raise Exception(f"HTTP catalog access failed: {e}")


async def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python validate_workflow.py <file.json>")
        print("\nExamples:")
        print("  python validate_workflow.py core/dsl/template_example.json")
        print("  python validate_workflow.py core/dsl/executable_example.json")
        print("  python validate_workflow.py core/dsl/dag_example.json")
        print("\nNote: This script requires the API server to be running with catalog data loaded.")
        print("Start the server with: python start_both.py")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not file_path.endswith('.json'):
        print("❌ Error: File must be a JSON file")
        sys.exit(1)
    
    result = await validate_workflow(file_path)
    
    if result:
        print("\n✅ Validation and linting completed!")
    else:
        print("\n❌ Failed to process file")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
