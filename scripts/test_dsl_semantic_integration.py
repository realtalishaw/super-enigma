#!/usr/bin/env python3
"""
Test script for the DSL generator with semantic search integration.
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.dsl_generator.generator import DSLGeneratorService
from services.dsl_generator.models import GenerationRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_semantic_integration():
    """Test the DSL generator with semantic search integration."""
    
    print("🧪 **Testing DSL Generator with Semantic Search Integration**")
    print("=" * 70)
    
    # Initialize the DSL generator service
    logger.info("Initializing DSL generator service...")
    generator = DSLGeneratorService()
    
    # Initialize the service
    await generator.initialize()
    
    # Test cases
    test_cases = [
        {
            "name": "Email workflow without selected apps",
            "request": GenerationRequest(
                user_prompt="I want to send an email when I receive a new message in Slack",
                selected_apps=None
            )
        },
        {
            "name": "Email workflow with selected apps",
            "request": GenerationRequest(
                user_prompt="Send an email notification",
                selected_apps=["gmail", "slack"]
            )
        },
        {
            "name": "Calendar workflow",
            "request": GenerationRequest(
                user_prompt="Create a calendar event when I get a new email",
                selected_apps=None
            )
        },
        {
            "name": "File management workflow",
            "request": GenerationRequest(
                user_prompt="Upload files to Google Drive when I receive them via email",
                selected_apps=["gmail", "googledrive"]
            )
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. **{test_case['name']}**")
        print(f"   Prompt: '{test_case['request'].user_prompt}'")
        if test_case['request'].selected_apps:
            print(f"   Selected apps: {test_case['request'].selected_apps}")
        
        try:
            # Test the retrieve step (semantic search)
            print("   🔍 Testing semantic retrieval...")
            relevant_tools = await generator._retrieve_relevant_tools(test_case['request'])
            
            if relevant_tools:
                triggers = relevant_tools.get('triggers', [])
                actions = relevant_tools.get('actions', [])
                providers = relevant_tools.get('providers', {})
                
                print(f"   ✅ Found {len(triggers)} triggers and {len(actions)} actions")
                print(f"   📊 Providers: {list(providers.keys())}")
                
                # Show top results
                if triggers:
                    top_trigger = triggers[0]
                    print(f"   🎯 Top trigger: {top_trigger.get('name', 'Unknown')} (score: {top_trigger.get('similarity_score', 0):.4f})")
                
                if actions:
                    top_action = actions[0]
                    print(f"   🎯 Top action: {top_action.get('name', 'Unknown')} (score: {top_action.get('similarity_score', 0):.4f})")
                
                # Test if selected apps filtering worked
                if test_case['request'].selected_apps:
                    found_providers = set()
                    for trigger in triggers:
                        if trigger.get('toolkit_slug'):
                            found_providers.add(trigger.get('toolkit_slug'))
                    for action in actions:
                        if action.get('toolkit_slug'):
                            found_providers.add(action.get('toolkit_slug'))
                    
                    expected_providers = set(test_case['request'].selected_apps)
                    if found_providers.issubset(expected_providers):
                        print("   ✅ Provider filtering working correctly")
                    else:
                        print(f"   ⚠️  Provider filtering issue: found {found_providers}, expected subset of {expected_providers}")
                
            else:
                print("   ❌ No relevant tools found")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            logger.error(f"Test case {i} failed: {e}")
    
    print("\n" + "=" * 70)
    print("✅ **Semantic search integration test completed!**")
    print("🎯 **Key improvements:**")
    print("   - Semantic understanding of user prompts")
    print("   - Provider filtering for selected apps")
    print("   - Relevance scoring for better tool selection")
    print("   - Fallback to original methods if needed")

if __name__ == "__main__":
    asyncio.run(test_semantic_integration())
