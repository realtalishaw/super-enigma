#!/usr/bin/env python3
"""
CLI tool for validating and linting workflow JSON files

Usage:
    python cli.py validate <file.json>
    python cli.py lint <file.json>
    python cli.py validate-and-lint <file.json>
    python cli.py --help
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Add the project root to the path so we can import core modules
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.validator import (
    validate, lint, Stage, LintContext, ValidateOptions, LintOptions
)
from core.validator.json_output import (
    validation_to_json, lint_to_json, comprehensive_to_dict
)


class RealCatalogAdapter:
    """Adapter to use the real catalog cache service"""
    
    def __init__(self, catalog_cache: Dict[str, Any]):
        self.catalog_cache = catalog_cache
    
    async def get_provider_by_slug(self, slug: str):
        """Get provider by slug from real catalog cache"""
        return self.catalog_cache.get(slug)
    
    async def get_tool_by_slug(self, action_name: str, toolkit_slug: str):
        """Get tool by slug from real catalog cache"""
        provider = self.catalog_cache.get(toolkit_slug)
        if not provider:
            return None
        
        actions = provider.get("actions", [])
        for action in actions:
            if action.get("name") == action_name:
                return action
        return None
    
    async def get_catalog(self):
        """Get full catalog data"""
        return {"providers": self.catalog_cache}


class EnhancedMockCatalog:
    """Enhanced mock catalog that provides more realistic data for testing"""
    
    async def get_provider_by_slug(self, slug: str):
        # More realistic mock data
        if slug == "gmail":
            return {
                "metadata": {"slug": "gmail"},
                "actions": [
                    {"name": "GMAIL_SEND_EMAIL", "parameters": [
                        {"name": "to", "type": "string", "required": True},
                        {"name": "subject", "type": "string", "required": True},
                        {"name": "body", "type": "string", "required": True}
                    ]},
                    {"name": "GMAIL_READ_EMAILS", "parameters": [
                        {"name": "query", "type": "string", "required": False},
                        {"name": "max_results", "type": "integer", "required": False}
                    ]},
                    {"name": "GMAIL_DELETE_EMAIL", "parameters": [
                        {"name": "message_id", "type": "string", "required": True}
                    ]}
                ],
                "triggers": [
                    {"name": "GMAIL_MESSAGE_RECEIVED", "parameters": [
                        {"name": "sender", "type": "string", "required": True},
                        {"name": "subject", "type": "string", "required": True}
                    ]},
                    {"name": "GMAIL_LABEL_CHANGED", "parameters": [
                        {"name": "label_id", "type": "string", "required": True}
                    ]}
                ]
            }
        elif slug == "slack":
            return {
                "metadata": {"slug": "slack"},
                "actions": [
                    {"name": "SLACK_SEND_MESSAGE", "parameters": [
                        {"name": "channel", "type": "string", "required": True},
                        {"name": "text", "type": "string", "required": True}
                    ]},
                    {"name": "SLACK_CREATE_CHANNEL", "parameters": [
                        {"name": "name", "type": "string", "required": True}
                    ]}
                ],
                "triggers": [
                    {"name": "SLACK_MESSAGE_RECEIVED", "parameters": [
                        {"name": "channel", "type": "string", "required": True},
                        {"name": "user", "type": "string", "required": True}
                    ]}
                ]
            }
        else:
            return {
                "metadata": {"slug": slug},
                "actions": [{"name": "mock_action", "parameters": []}],
                "triggers": [{"name": "mock_trigger", "parameters": []}]
            }
    
    async def get_tool_by_slug(self, action_name: str, toolkit_slug: str):
        provider = await self.get_provider_by_slug(toolkit_slug)
        if not provider:
            return None
        
        actions = provider.get("actions", [])
        for action in actions:
            if action.get("name") == action_name:
                return action
        return None
    
    async def get_catalog(self):
        return {
            "providers": {
                "gmail": await self.get_provider_by_slug("gmail"),
                "slack": await self.get_provider_by_slug("slack")
            }
        }


class MockConnections:
    """Mock connections for CLI usage when real connections are not available"""
    
    async def get_connection(self, connection_id: str):
        # Mock connection data
        return {
            "connection_id": connection_id,
            "scopes": ["read", "write"]
        }


async def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load and parse a JSON file"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File '{file_path}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in '{file_path}': {e}")
        sys.exit(1)


def determine_stage(doc: Dict[str, Any]) -> Stage:
    """Determine the workflow stage from the document"""
    schema_type = doc.get("schema_type", "").lower()
    
    if schema_type == "template":
        return Stage.TEMPLATE
    elif schema_type == "executable":
        return Stage.EXECUTABLE
    elif schema_type == "dag":
        return Stage.DAG
    else:
        print(f"⚠️  Warning: Unknown schema_type '{schema_type}', defaulting to TEMPLATE")
        return Stage.TEMPLATE


async def get_real_catalog_context():
    """Try to get real catalog context from Redis cache, fallback to enhanced mock if not available"""
    try:
        # Try to import and use the real cache service
        from api.cache_service import global_cache_service
        
        # Check if the cache service is initialized and has data
        if (global_cache_service.is_initialized() and 
            global_cache_service.get_catalog_cache()):
            
            catalog_cache = global_cache_service.get_catalog_cache()
            provider_count = len(catalog_cache)
            
            print(f"🔗 Using REAL Redis catalog cache with {provider_count} providers")
            
            # Log some sample providers for debugging
            if catalog_cache:
                sample_providers = list(catalog_cache.keys())[:5]
                print(f"📚 Sample providers: {', '.join(sample_providers)}")
                
                # Show some sample actions and triggers
                for provider_key in sample_providers[:3]:
                    provider = catalog_cache[provider_key]
                    actions_count = len(provider.get('actions', []))
                    triggers_count = len(provider.get('triggers', []))
                    print(f"  📦 {provider_key}: {actions_count} actions, {triggers_count} triggers")
            
            return LintContext(
                catalog=RealCatalogAdapter(catalog_cache),
                connections=MockConnections()
            )
        else:
            print("⚠️  Real catalog cache not available or empty")
            print("💡 Make sure your API server is running and has loaded catalog data")
            print("💡 You can start the server with: python start_both.py")
            
            # Try to refresh the cache
            try:
                print("🔄 Attempting to refresh cache...")
                await global_cache_service.refresh_cache(force=True)
                
                if global_cache_service.get_catalog_cache():
                    catalog_cache = global_cache_service.get_catalog_cache()
                    print(f"✅ Cache refreshed successfully! Found {len(catalog_cache)} providers")
                    return LintContext(
                        catalog=RealCatalogAdapter(catalog_cache),
                        connections=MockConnections()
                    )
                else:
                    print("❌ Cache refresh failed - no data available")
            except Exception as e:
                print(f"❌ Cache refresh failed: {e}")
            
            print("⚠️  Falling back to enhanced mock data for testing")
            return LintContext(
                catalog=EnhancedMockCatalog(),
                connections=MockConnections()
            )
            
    except ImportError as e:
        print(f"⚠️  Real catalog service not available: {e}")
        print("💡 Make sure you're running from the project root directory")
        print("⚠️  Using enhanced mock data for testing")
        return LintContext(
            catalog=EnhancedMockCatalog(),
            connections=MockConnections()
        )
    except Exception as e:
        print(f"❌ Error accessing catalog service: {e}")
        print("⚠️  Using enhanced mock data for testing")
        return LintContext(
            catalog=EnhancedMockCatalog(),
            connections=MockConnections()
        )


async def run_validation(doc: Dict[str, Any], stage: Stage, opts: Optional[ValidateOptions] = None) -> str:
    """Run validation and return JSON result"""
    try:
        result = await validate(stage, doc, opts)
        return validation_to_json(result, pretty=True)
    except Exception as e:
        return json.dumps({
            "error": "Validation failed",
            "message": str(e),
            "type": "validation_error"
        }, indent=2)


async def run_linting(doc: Dict[str, Any], stage: Stage, opts: Optional[LintOptions] = None) -> str:
    """Run linting and return JSON result"""
    try:
        # Try to get real catalog context, fallback to enhanced mock
        context = await get_real_catalog_context()
        
        result = await lint(stage, doc, context, opts)
        return lint_to_json(result, pretty=True)
    except Exception as e:
        return json.dumps({
            "error": "Linting failed",
            "message": str(e),
            "type": "linting_error"
        }, indent=2)


async def run_validation_and_linting(doc: Dict[str, Any], stage: Stage) -> str:
    """Run both validation and linting and return comprehensive JSON result"""
    try:
        # Try to get real catalog context, fallback to enhanced mock
        context = await get_real_catalog_context()
        
        # Run validation
        validation_result = await validate(stage, doc)
        
        # Run linting
        lint_result = await lint(stage, doc, context)
        
        # Get comprehensive report
        comprehensive = comprehensive_to_dict(validation_result, lint_result)
        return json.dumps(comprehensive, indent=2, default=str)
        
    except Exception as e:
        return json.dumps({
            "error": "Validation and linting failed",
            "message": str(e),
            "type": "comprehensive_error"
        }, indent=2)


def print_summary(doc: Dict[str, Any], stage: Stage):
    """Print a summary of the document being processed"""
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


async def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="Validate and lint workflow JSON files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py validate template_example.json
  python cli.py lint executable_workflow.json
  python cli.py validate-and-lint my_workflow.json
        """
    )
    
    parser.add_argument(
        "command",
        choices=["validate", "lint", "validate-and-lint"],
        help="Command to run"
    )
    
    parser.add_argument(
        "file",
        help="JSON file to process"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Output file for results (default: stdout)"
    )
    
    parser.add_argument(
        "--fast", "-f",
        action="store_true",
        help="Enable fast validation mode"
    )
    
    parser.add_argument(
        "--strict", "-s",
        action="store_true",
        help="Enable strict linting mode"
    )
    
    parser.add_argument(
        "--use-mock", "-m",
        action="store_true",
        help="Force use of mock catalog data (for testing)"
    )
    
    args = parser.parse_args()
    
    # Load the JSON file
    print(f"🚀 Loading file: {args.file}")
    doc = await load_json_file(args.file)
    
    # Determine the stage
    stage = determine_stage(doc)
    
    # Print summary
    print_summary(doc, stage)
    
    # Run the requested command
    result = ""
    
    if args.command == "validate":
        print("🔍 Running validation...")
        opts = ValidateOptions(fast=args.fast)
        result = await run_validation(doc, stage, opts)
        
    elif args.command == "lint":
        print("🧹 Running linting...")
        opts = LintOptions(level="strict" if args.strict else "standard")
        result = await run_linting(doc, stage, opts)
        
    elif args.command == "validate-and-lint":
        print("🔍 Running validation and linting...")
        result = await run_validation_and_linting(doc, stage)
    
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            f.write(result)
        print(f"💾 Results saved to: {args.output}")
    else:
        print("\n📋 Results:")
        print(result)
    
    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
