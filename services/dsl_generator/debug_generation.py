"""
Debug Script for DSL Generator

This script helps troubleshoot workflow generation issues by testing
individual components and providing detailed logging.
"""

import asyncio
import logging
import json
from typing import Dict, Any

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import components
from .catalog_manager import CatalogManager
from .context_builder import ContextBuilder
from .prompt_builder import PromptBuilder
from .ai_client import AIClient
from .response_parser import ResponseParser
from .models import GenerationRequest

logger = logging.getLogger(__name__)


async def debug_catalog_manager():
    """Debug catalog manager functionality"""
    print("\n🔍 Debugging Catalog Manager...")
    
    try:
        catalog_manager = CatalogManager()
        await catalog_manager.initialize()
        
        cache_status = catalog_manager.get_cache_status()
        print(f"✅ Cache Status: {cache_status}")
        
        catalog_summary = catalog_manager.get_catalog_summary()
        print(f"✅ Catalog Summary: {catalog_summary}")
        
        return catalog_manager
    except Exception as e:
        print(f"❌ Catalog Manager Error: {e}")
        return None


async def debug_context_builder(catalog_manager: CatalogManager):
    """Debug context builder functionality"""
    print("\n🔍 Debugging Context Builder...")
    
    try:
        context_builder = ContextBuilder(catalog_manager)
        
        request = GenerationRequest(
            user_prompt="Send a Slack message when a new email arrives",
            workflow_type="template",
            complexity="simple"
        )
        
        context = await context_builder.build_generation_context(request)
        print(f"✅ Context built successfully")
        print(f"   - Providers: {len(context.catalog.available_providers)}")
        print(f"   - Triggers: {len(context.catalog.available_triggers)}")
        print(f"   - Actions: {len(context.catalog.available_actions)}")
        
        return context_builder, context
    except Exception as e:
        print(f"❌ Context Builder Error: {e}")
        return None, None


async def debug_prompt_builder(context):
    """Debug prompt builder functionality"""
    print("\n🔍 Debugging Prompt Builder...")
    
    try:
        prompt_builder = PromptBuilder()
        prompt = prompt_builder.build_prompt(context, 1, [])
        
        print(f"✅ Prompt generated successfully")
        print(f"   - Length: {len(prompt)} characters")
        print(f"   - Preview: {prompt[:200]}...")
        
        return prompt_builder, prompt
    except Exception as e:
        print(f"❌ Prompt Builder Error: {e}")
        return None, None


async def debug_ai_client():
    """Debug AI client functionality"""
    print("\n🔍 Debugging AI Client...")
    
    try:
        ai_client = AIClient()
        info = ai_client.get_model_info()
        
        print(f"✅ AI Client Info: {info}")
        
        if ai_client.is_configured():
            print("✅ AI Client is properly configured")
        else:
            print("⚠️  AI Client needs API key configuration")
        
        return ai_client
    except Exception as e:
        print(f"❌ AI Client Error: {e}")
        return None


async def debug_response_parser():
    """Debug response parser functionality"""
    print("\n🔍 Debugging Response Parser...")
    
    try:
        response_parser = ResponseParser()
        
        # Test with a valid template
        valid_template = {
            "schema_type": "template",
            "workflow": {
                "name": "Test Workflow",
                "description": "A test workflow",
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
            "missing_information": [
                {
                    "field": "slack_channel",
                    "prompt": "Which Slack channel?",
                    "type": "string",
                    "required": True
                }
            ],
            "confidence": 85
        }
        
        # Test structure validation
        is_valid = response_parser._validate_dsl_structure(valid_template)
        print(f"✅ Structure validation test: {is_valid}")
        
        # Test structure fix
        incomplete_template = {"schema_type": "template"}
        fixed_template = response_parser._attempt_structure_fix(incomplete_template)
        print(f"✅ Structure fix test: {list(fixed_template.keys())}")
        
        return response_parser
    except Exception as e:
        print(f"❌ Response Parser Error: {e}")
        return None


async def debug_full_generation():
    """Debug the full generation process"""
    print("\n🔍 Debugging Full Generation Process...")
    
    try:
        # Initialize components
        catalog_manager = await debug_catalog_manager()
        if not catalog_manager:
            return
        
        context_builder, context = await debug_context_builder(catalog_manager)
        if not context:
            return
        
        prompt_builder, prompt = await debug_prompt_builder(context)
        if not prompt:
            return
        
        ai_client = await debug_ai_client()
        if not ai_client or not ai_client.is_configured():
            print("⚠️  Skipping AI call due to missing API key")
            return
        
        # Test AI call (if configured)
        print("\n🔍 Testing AI Call...")
        try:
            response = await ai_client.generate_workflow(prompt)
            print(f"✅ AI call successful, response length: {len(response)}")
            
            # Test response parsing
            response_parser = await debug_response_parser()
            if response_parser:
                print("\n🔍 Testing Response Parsing...")
                parsed_response = await response_parser.parse_response(response, context)
                if parsed_response.success:
                    print(f"✅ Response parsing successful")
                    print(f"   - Confidence: {parsed_response.confidence}")
                    print(f"   - Missing fields: {len(parsed_response.missing_fields)}")
                else:
                    print(f"❌ Response parsing failed: {parsed_response.error_message}")
        
        except Exception as e:
            print(f"❌ AI call failed: {e}")
    
    except Exception as e:
        print(f"❌ Full generation debug failed: {e}")


async def main():
    """Run all debug functions"""
    print("🚀 DSL Generator Debug Script")
    print("=" * 50)
    
    # Run individual component debugs
    await debug_catalog_manager()
    await debug_context_builder(CatalogManager())
    await debug_prompt_builder(None)
    await debug_ai_client()
    await debug_response_parser()
    
    # Run full generation debug
    await debug_full_generation()
    
    print("\n🎉 Debug completed!")
    print("\nCheck the logs above for any issues.")


if __name__ == "__main__":
    asyncio.run(main())
