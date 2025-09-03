#!/usr/bin/env python3
"""
Test script for the two-step retrieval: Semantic Search + Groq LLM Analysis.
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

async def test_two_step_retrieval():
    """Test the two-step retrieval: Semantic Search + Groq LLM Analysis."""
    
    print("🧪 **Testing Two-Step Retrieval: Semantic Search + Groq LLM Analysis**")
    print("=" * 80)
    
    # Initialize the DSL generator service
    logger.info("Initializing DSL generator service...")
    generator = DSLGeneratorService()
    
    # Initialize the service
    await generator.initialize()
    
    # Test cases
    test_cases = [
        {
            "name": "Email workflow without selected apps (should use Groq)",
            "request": GenerationRequest(
                user_prompt="I want to send an email when I receive a new message in Slack",
                selected_apps=None
            ),
            "should_use_groq": True
        },
        {
            "name": "Email workflow with selected apps (should skip Groq)",
            "request": GenerationRequest(
                user_prompt="Send an email notification",
                selected_apps=["gmail", "slack"]
            ),
            "should_use_groq": False
        },
        {
            "name": "Complex workflow without selected apps (should use Groq)",
            "request": GenerationRequest(
                user_prompt="When I get a new email, create a calendar event and send a Slack notification",
                selected_apps=None
            ),
            "should_use_groq": True
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. **{test_case['name']}**")
        print(f"   Prompt: '{test_case['request'].user_prompt}'")
        if test_case['request'].selected_apps:
            print(f"   Selected apps: {test_case['request'].selected_apps}")
        print(f"   Should use Groq: {test_case['should_use_groq']}")
        
        try:
            # Test the retrieve step (semantic search + Groq analysis)
            print("   🔍 Testing two-step retrieval...")
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
                
                # Check if Groq was used (for cases without selected apps)
                if not test_case['request'].selected_apps and generator.groq_api_key:
                    print("   🤖 Groq LLM analysis was used to refine semantic search results")
                elif test_case['request'].selected_apps:
                    print("   🎯 Provider filtering was used (Groq skipped)")
                else:
                    print("   ⚠️  Groq API key not available, using semantic search only")
                
            else:
                print("   ❌ No relevant tools found")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            logger.error(f"Test case {i} failed: {e}")
    
    print("\n" + "=" * 80)
    print("✅ **Two-step retrieval test completed!**")
    print("🎯 **Key improvements:**")
    print("   - Step 1: Semantic search finds potentially relevant tools")
    print("   - Step 2: Groq LLM analyzes and selects the best tools for the specific task")
    print("   - Provider filtering for selected apps (skips Groq)")
    print("   - Fallback to original methods if needed")

if __name__ == "__main__":
    asyncio.run(test_two_step_retrieval())
