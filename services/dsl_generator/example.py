"""
Example usage of the DSL LLM Generator service.

This script demonstrates how to use the service to generate workflow templates
from natural language prompts.
"""

import asyncio
import json
import os
from typing import List

from .generator import DSLGeneratorService
from .models import GenerationRequest


async def example_basic_generation():
    """Example of basic workflow generation"""
    print("🚀 Example 1: Basic Workflow Generation")
    print("=" * 50)
    
    # Create a simple request
    request = GenerationRequest(
        user_prompt="Send me a Slack notification when I receive an important email",
        workflow_type="template",
        complexity="simple"
    )
    
    # Initialize and run the generator
    generator = DSLGeneratorService()
    await generator.initialize()
    
    print(f"📝 User Request: {request.user_prompt}")
    print(f"🔧 Workflow Type: {request.workflow_type}")
    print(f"📊 Complexity: {request.complexity}")
    print()
    
    print("📡 Generating workflow...")
    response = await generator.generate_workflow(request)
    
    if response.success:
        print("✅ Workflow generated successfully!")
        print(f"   Confidence: {response.confidence:.2f}")
        print(f"   Missing fields: {len(response.missing_fields)}")
        
        if response.suggested_apps:
            print(f"   Suggested apps: {', '.join(response.suggested_apps)}")
        
        # Show missing fields
        if response.missing_fields:
            print("\n📝 Missing fields that need user input:")
            for field in response.missing_fields:
                print(f"   - {field.field}: {field.prompt}")
        
        # Show generated DSL
        print("\n📄 Generated DSL Template:")
        print(json.dumps(response.dsl_template, indent=2))
        
    else:
        print(f"❌ Generation failed: {response.error_message}")
    
    print("\n" + "=" * 50 + "\n")


async def example_app_specific_generation():
    """Example of generation with specific app selection"""
    print("🚀 Example 2: App-Specific Generation")
    print("=" * 50)
    
    # Create a request with specific apps
    request = GenerationRequest(
        user_prompt="Create a workflow to backup important files to Google Drive and notify me on Slack",
        selected_apps=["gmail", "googledrive", "slack"],
        workflow_type="template",
        complexity="medium"
    )
    
    # Initialize and run the generator
    generator = DSLGeneratorService()
    await generator.initialize()
    
    print(f"📝 User Request: {request.user_prompt}")
    print(f"🔧 Workflow Type: {request.workflow_type}")
    print(f"📊 Complexity: {request.complexity}")
    print(f"📱 Selected Apps: {', '.join(request.selected_apps)}")
    print()
    
    print("📡 Generating workflow...")
    response = await generator.generate_workflow(request)
    
    if response.success:
        print("✅ Workflow generated successfully!")
        print(f"   Confidence: {response.confidence:.2f}")
        print(f"   Missing fields: {len(response.missing_fields)}")
        
        if response.suggested_apps:
            print(f"   Suggested apps: {', '.join(response.suggested_apps)}")
        
        # Show missing fields
        if response.missing_fields:
            print("\n📝 Missing fields that need user input:")
            for field in response.missing_fields:
                print(f"   - {field.field}: {field.prompt}")
        
        # Show generated DSL
        print("\n📄 Generated DSL Template:")
        print(json.dumps(response.dsl_template, indent=2))
        
    else:
        print(f"❌ Generation failed: {response.error_message}")
    
    print("\n" + "=" * 50 + "\n")


async def example_complex_workflow():
    """Example of complex workflow generation"""
    print("🚀 Example 3: Complex Workflow Generation")
    print("=" * 50)
    
    # Create a complex request
    request = GenerationRequest(
        user_prompt="Build a sophisticated CRM workflow that monitors customer interactions, sends follow-up emails, creates tasks in project management, and generates weekly reports",
        workflow_type="dag",
        complexity="complex"
    )
    
    # Initialize and run the generator
    generator = DSLGeneratorService()
    await generator.initialize()
    
    print(f"📝 User Request: {request.user_prompt}")
    print(f"🔧 Workflow Type: {request.workflow_type}")
    print(f"📊 Complexity: {request.complexity}")
    print()
    
    print("📡 Generating workflow...")
    response = await generator.generate_workflow(request)
    
    if response.success:
        print("✅ Workflow generated successfully!")
        print(f"   Confidence: {response.confidence:.2f}")
        print(f"   Missing fields: {len(response.missing_fields)}")
        
        if response.suggested_apps:
            print(f"   Suggested apps: {', '.join(response.suggested_apps)}")
        
        # Show missing fields
        if response.missing_fields:
            print("\n📝 Missing fields that need user input:")
            for field in response.missing_fields:
                print(f"   - {field.field}: {field.prompt}")
        
        # Show generated DSL
        print("\n📄 Generated DSL Template:")
        print(json.dumps(response.dsl_template, indent=2))
        
    else:
        print(f"❌ Generation failed: {response.error_message}")
    
    print("\n" + "=" * 50 + "\n")


async def example_executable_workflow():
    """Example of executable workflow generation"""
    print("🚀 Example 4: Executable Workflow Generation")
    print("=" * 50)
    
    # Create an executable request
    request = GenerationRequest(
        user_prompt="Create a workflow that sends a daily summary email with weather information and calendar events",
        workflow_type="executable",
        complexity="medium"
    )
    
    # Initialize and run the generator
    generator = DSLGeneratorService()
    await generator.initialize()
    
    print(f"📝 User Request: {request.user_prompt}")
    print(f"🔧 Workflow Type: {request.workflow_type}")
    print(f"📊 Complexity: {request.complexity}")
    print()
    
    print("📡 Generating workflow...")
    response = await generator.generate_workflow(request)
    
    if response.success:
        print("✅ Workflow generated successfully!")
        print(f"   Confidence: {response.confidence:.2f}")
        print(f"   Missing fields: {len(response.missing_fields)}")
        
        if response.suggested_apps:
            print(f"   Suggested apps: {', '.join(response.suggested_apps)}")
        
        # Show missing fields
        if response.missing_fields:
            print("\n📝 Missing fields that need user input:")
            for field in response.missing_fields:
                print(f"   - {field.field}: {field.prompt}")
        
        # Show generated DSL
        print("\n📄 Generated DSL Template:")
        print(json.dumps(response.dsl_template, indent=2))
        
    else:
        print(f"❌ Generation failed: {response.error_message}")
    
    print("\n" + "=" * 50 + "\n")


async def main():
    """Run all examples"""
    print("🎯 DSL LLM Generator Service Examples")
    print("=" * 60)
    print()
    
    # Check for required environment variables
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY environment variable is required")
        print("Set it with: export ANTHROPIC_API_KEY=your_api_key_here")
        return
    
    try:
        # Run examples
        await example_basic_generation()
        await example_app_specific_generation()
        await example_complex_workflow()
        await example_executable_workflow()
        
        print("🎉 All examples completed successfully!")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
