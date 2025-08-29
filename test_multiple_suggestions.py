#!/usr/bin/env python3
"""
Test script for the new multiple suggestions functionality.
This script demonstrates how to use the updated API to generate multiple workflow suggestions.
"""

import asyncio
import json
import sys
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.dsl_generator.generator import DSLGeneratorService
from services.dsl_generator.models import GenerationRequest


async def test_multiple_suggestions():
    """Test the multiple suggestions generation functionality"""
    
    print("🚀 Testing Multiple Suggestions Generation")
    print("=" * 50)
    
    # Initialize the generator service
    print("1. Initializing DSL Generator Service...")
    generator = DSLGeneratorService()
    await generator.initialize()
    print("✅ Generator initialized")
    
    # Test case 1: Single suggestion (default behavior)
    print("\n2. Testing Single Suggestion Generation...")
    single_request = GenerationRequest(
        user_prompt="Send a notification when a new email arrives",
        selected_apps=["gmail"]
    )
    
    start_time = asyncio.get_event_loop().time()
    single_response = await generator.generate_workflow(single_request)
    single_time = (asyncio.get_event_loop().time() - start_time) * 1000
    
    print(f"✅ Single generation completed in {single_time:.0f}ms")
    print(f"   Success: {single_response.success}")
    if single_response.success:
        print(f"   Workflow name: {single_response.dsl_template.get('workflow', {}).get('name', 'Unknown')}")
        print(f"   Confidence: {single_response.confidence:.2f}")
    
    # Test case 2: Multiple suggestions (new functionality)
    print("\n3. Testing Multiple Suggestions Generation...")
    num_suggestions = 3
    
    start_time = asyncio.get_event_loop().time()
    multiple_responses = await generator.generate_multiple_workflows(single_request, num_suggestions)
    multiple_time = (asyncio.get_event_loop().time() - start_time) * 1000
    
    print(f"✅ Multiple generation ({num_suggestions} workflows) completed in {multiple_time:.0f}ms")
    print(f"   Speedup: {single_time / multiple_time:.2f}x faster than sequential generation")
    print(f"   Generated {len(multiple_responses)} workflows")
    
    # Display results
    print("\n4. Generated Workflows:")
    print("-" * 30)
    
    for i, response in enumerate(multiple_responses):
        print(f"\nWorkflow {i+1}:")
        if response.success:
            workflow = response.dsl_template.get('workflow', {})
            print(f"  ✅ Title: {workflow.get('name', 'Unknown')}")
            print(f"  📝 Description: {workflow.get('description', 'No description')}")
            print(f"  🎯 Confidence: {response.confidence:.2f}")
            print(f"  🔧 Triggers: {len(workflow.get('triggers', []))}")
            print(f"  ⚡ Actions: {len(workflow.get('actions', []))}")
        else:
            print(f"  ❌ Failed: {response.error_message}")
    
    # Test case 3: Edge cases
    print("\n5. Testing Edge Cases...")
    
    # Test with invalid number
    try:
        invalid_responses = await generator.generate_multiple_workflows(single_request, 0)
        print("❌ Should have failed with 0 suggestions")
    except ValueError as e:
        print(f"✅ Correctly rejected invalid input: {e}")
    
    try:
        invalid_responses = await generator.generate_multiple_workflows(single_request, 6)
        print("❌ Should have failed with 6 suggestions")
    except ValueError as e:
        print(f"✅ Correctly rejected invalid input: {e}")
    
    print("\n🎉 Multiple Suggestions Test Complete!")
    print(f"   Single generation time: {single_time:.0f}ms")
    print(f"   Multiple generation time: {multiple_time:.0f}ms")
    print(f"   Parallel efficiency: {single_time / multiple_time:.2f}x")


if __name__ == "__main__":
    print("Starting Multiple Suggestions Test...")
    print("Note: This requires proper API keys and catalog setup.")
    print()
    
    try:
        asyncio.run(test_multiple_suggestions())
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print("Make sure you have:")
        print("1. Set ANTHROPIC_API_KEY and GROQ_API_KEY environment variables")
        print("2. Run the catalog setup script first")
        print("3. Have the cache service running")
