#!/usr/bin/env python3
"""
Test script to verify planning step field name fixes
"""

import asyncio
import sys
import os

# Add the services directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services', 'dsl_generator'))

from prompt_builder import PromptBuilder
from models import GenerationContext, GenerationRequest

async def test_planning_prompt():
    """Test the planning prompt to ensure it generates correct field names"""
    print("Testing planning prompt field names...")
    
    # Create a mock context
    context = GenerationContext(
        request=GenerationRequest(
            user_prompt="When a new email arrives in Gmail, send a Slack message",
            workflow_type="template",
            complexity="simple",
            selected_apps=["gmail", "slack"]
        ),
        catalog_data={
            "gmail": {
                "name": "Gmail",
                "triggers": ["GMAIL_NEW_GMAIL_MESSAGE"],
                "actions": ["GMAIL_SEND_EMAIL"]
            },
            "slack": {
                "name": "Slack", 
                "triggers": ["SLACK_MESSAGE_RECEIVED"],
                "actions": ["SLACK_POST_MESSAGE"]
            }
        }
    )
    
    # Create prompt builder
    prompt_builder = PromptBuilder()
    
    # Test planning prompt
    print("\n1. Testing planning prompt...")
    planning_prompt = prompt_builder.build_planning_prompt(context)
    
    # Check if the planning prompt uses the correct field names
    if "composio_trigger_slug" in planning_prompt:
        print("  ✅ Planning prompt uses 'composio_trigger_slug' (correct)")
    else:
        print("  ❌ Planning prompt missing 'composio_trigger_slug'")
    
    if "trigger_id" in planning_prompt:
        print("  ❌ Planning prompt still contains 'trigger_id' (incorrect)")
    else:
        print("  ✅ Planning prompt does not contain 'trigger_id' (correct)")
    
    if "action_name" in planning_prompt:
        print("  ✅ Planning prompt uses 'action_name' (correct)")
    else:
        print("  ❌ Planning prompt missing 'action_name'")
    
    # Test template prompt
    print("\n2. Testing template prompt...")
    template_prompt = prompt_builder.build_prompt(context, 1, [], '{}')
    
    # Check if the template prompt uses the correct field names
    if "composio_trigger_slug" in template_prompt:
        print("  ✅ Template prompt uses 'composio_trigger_slug' (correct)")
    else:
        print("  ❌ Template prompt missing 'composio_trigger_slug'")
    
    if "trigger_id" in template_prompt:
        print("  ❌ Template prompt still contains 'trigger_id' (incorrect)")
    else:
        print("  ✅ Template prompt does not contain 'trigger_id' (correct)")
    
    # Test executable prompt
    print("\n3. Testing executable prompt...")
    context.request.workflow_type = "executable"
    executable_prompt = prompt_builder.build_prompt(context, 1, [], '{}')
    
    if "composio_trigger_slug" in executable_prompt:
        print("  ✅ Executable prompt uses 'composio_trigger_slug' (correct)")
    else:
        print("  ❌ Executable prompt missing 'composio_trigger_slug'")
    
    # Test DAG prompt
    print("\n4. Testing DAG prompt...")
    context.request.workflow_type = "dag"
    dag_prompt = prompt_builder.build_prompt(context, 1, [], '{}')
    
    if "composio_trigger_slug" in dag_prompt:
        print("  ✅ DAG prompt uses 'composio_trigger_slug' (correct)")
    else:
        print("  ❌ DAG prompt missing 'composio_trigger_slug'")
    
    print("\nPlanning prompt field name test completed!")

async def main():
    """Main test function"""
    await test_planning_prompt()
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
