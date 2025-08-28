"""
Example: Using the Modular DSL Generator Components

This script demonstrates how to use the individual components
of the DSL generator service independently.
"""

import asyncio
import json
import logging
from typing import Dict, Any

# Import the modular components
from .catalog_manager import CatalogManager
from .context_builder import ContextBuilder
from .prompt_builder import PromptBuilder
from .ai_client import AIClient
from .response_parser import ResponseParser
from .workflow_validator import WorkflowValidator
from .models import GenerationRequest, GenerationContext

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demonstrate_catalog_manager():
    """Demonstrate the catalog manager functionality"""
    print("\n=== Catalog Manager Demo ===")
    
    catalog_manager = CatalogManager()
    
    # Initialize the catalog manager
    await catalog_manager.initialize()
    
    # Get cache status
    cache_status = catalog_manager.get_cache_status()
    print(f"Cache Status: {cache_status}")
    
    # Get catalog summary
    summary = catalog_manager.get_catalog_summary()
    print(f"Catalog Summary: {summary}")
    
    return catalog_manager


async def demonstrate_context_builder(catalog_manager: CatalogManager):
    """Demonstrate the context builder functionality"""
    print("\n=== Context Builder Demo ===")
    
    context_builder = ContextBuilder(catalog_manager)
    
    # Create a sample request
    request = GenerationRequest(
        user_prompt="Send a Slack message when a new email arrives",
        workflow_type="template",
        complexity="simple"
    )
    
    # Build generation context
    context = await context_builder.build_generation_context(request)
    print(f"Context built with {len(context.catalog.available_providers)} providers")
    
    return context_builder, context


async def demonstrate_prompt_builder(context: GenerationContext):
    """Demonstrate the prompt builder functionality"""
    print("\n=== Prompt Builder Demo ===")
    
    prompt_builder = PromptBuilder()
    
    # Build a prompt
    prompt = prompt_builder.build_prompt(context, 1, [])
    print(f"Generated prompt length: {len(prompt)} characters")
    print(f"Prompt preview: {prompt[:200]}...")
    
    return prompt_builder


async def demonstrate_ai_client():
    """Demonstrate the AI client functionality"""
    print("\n=== AI Client Demo ===")
    
    # Note: This requires a valid API key
    ai_client = AIClient()
    
    # Get client info
    info = ai_client.get_model_info()
    print(f"AI Client Info: {info}")
    
    # Check if configured
    if ai_client.is_configured():
        print("✅ AI Client is properly configured")
    else:
        print("⚠️  AI Client needs API key configuration")
    
    return ai_client


async def demonstrate_response_parser():
    """Demonstrate the response parser functionality"""
    print("\n=== Response Parser Demo ===")
    
    response_parser = ResponseParser()
    
    # Sample Claude response (simulated)
    sample_response = '''
    Here's your workflow:
    {
        "schema_type": "template",
        "workflow": {
            "triggers": [
                {
                    "toolkit_slug": "gmail",
                    "trigger_id": "new_email"
                }
            ],
            "actions": [
                {
                    "toolkit_slug": "slack",
                    "action_name": "send_message"
                }
            ]
        },
        "toolkit": {
            "slug": "workflow_automation"
        },
        "missing_information": [
            {
                "field": "slack_channel",
                "prompt": "Which Slack channel should receive the message?",
                "type": "string",
                "required": true
            }
        ]
    }
    '''
    
    # Create a minimal context for parsing
    context = GenerationContext(
        request=GenerationRequest(
            user_prompt="Test",
            workflow_type="template",
            complexity="simple"
        ),
        catalog=None,
        schema_definition={}
    )
    
    # Parse the response
    parsed_response = await response_parser.parse_response(sample_response, context)
    
    if parsed_response.success:
        print(f"✅ Parsed successfully with confidence: {parsed_response.confidence}")
        print(f"Missing fields: {len(parsed_response.missing_fields)}")
        print(f"Suggested apps: {parsed_response.suggested_apps}")
    else:
        print(f"❌ Parsing failed: {parsed_response.error_message}")
    
    return response_parser


async def demonstrate_workflow_validator():
    """Demonstrate the workflow validator functionality"""
    print("\n=== Workflow Validator Demo ===")
    
    workflow_validator = WorkflowValidator()
    
    # Sample workflow data
    sample_workflow = {
        "schema_type": "template",
        "workflow": {
            "triggers": [
                {
                    "toolkit_slug": "gmail",
                    "trigger_id": "new_email"
                }
            ],
            "actions": [
                {
                    "toolkit_slug": "slack",
                    "action_name": "send_message"
                }
            ]
        },
        "toolkit": {
            "slug": "workflow_automation"
        }
    }
    
    # Sample catalog data
    sample_catalog = {
        "gmail": {
            "slug": "gmail",
            "name": "Gmail",
            "triggers": [{"id": "new_email", "name": "New Email"}],
            "actions": []
        },
        "slack": {
            "slug": "slack",
            "name": "Slack",
            "triggers": [],
            "actions": [{"action_name": "send_message", "name": "Send Message"}]
        }
    }
    
    # Validate catalog compliance
    compliance = workflow_validator.verify_catalog_compliance(sample_workflow, sample_catalog)
    print(f"Catalog Compliance: {compliance}")
    
    return workflow_validator


async def demonstrate_full_integration():
    """Demonstrate how all components work together"""
    print("\n=== Full Integration Demo ===")
    
    try:
        # Initialize all components
        catalog_manager = await demonstrate_catalog_manager()
        context_builder, context = await demonstrate_context_builder(catalog_manager)
        prompt_builder = await demonstrate_prompt_builder(context)
        ai_client = await demonstrate_ai_client()
        response_parser = await demonstrate_response_parser()
        workflow_validator = await demonstrate_workflow_validator()
        
        print("\n✅ All components initialized successfully!")
        print("\nComponent Summary:")
        print(f"- Catalog Manager: {catalog_manager.get_cache_status()['provider_count']} providers")
        print(f"- Context Builder: Ready")
        print(f"- Prompt Builder: Ready")
        print(f"- AI Client: {'Configured' if ai_client.is_configured() else 'Needs API Key'}")
        print(f"- Response Parser: Ready")
        print(f"- Workflow Validator: Ready")
        
    except Exception as e:
        print(f"❌ Integration demo failed: {e}")


async def main():
    """Run all demonstrations"""
    print("🚀 DSL Generator Modular Components Demo")
    print("=" * 50)
    
    # Run individual component demos
    await demonstrate_catalog_manager()
    await demonstrate_context_builder(CatalogManager())
    await demonstrate_prompt_builder(None)  # Will create minimal context
    await demonstrate_ai_client()
    await demonstrate_response_parser()
    await demonstrate_workflow_validator()
    
    # Run full integration demo
    await demonstrate_full_integration()
    
    print("\n🎉 Demo completed!")
    print("\nTo use the full service:")
    print("from services.dsl_generator import DSLGeneratorService")
    print("generator = DSLGeneratorService(anthropic_api_key='your-key')")


if __name__ == "__main__":
    asyncio.run(main())
