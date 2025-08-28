"""
CLI interface for testing the DSL LLM Generator service.
"""

import asyncio
import json
import sys
import os
from typing import Optional

from .generator import DSLGeneratorService
from .models import GenerationRequest


async def main():
    """Main CLI function"""
    if len(sys.argv) < 2:
        print("Usage: python -m services.dsl_generator.cli <user_prompt> [options]")
        print("\nOptions:")
        print("  --apps <app1,app2>     Comma-separated list of app slugs")
        print("  --type <type>          Workflow type: template, executable, or dag")
        print("  --complexity <level>   Complexity: simple, medium, or complex")
        print("  --user-id <id>         User ID for tracking")
        print("  --output <file>        Output file for the generated DSL")
        print("\nExamples:")
        print("  python -m services.dsl_generator.cli 'Send me a Slack notification when I receive an important email'")
        print("  python -m services.dsl_generator.cli 'Create a workflow to backup files to Google Drive' --apps gmail,slack,googledrive --type template")
        sys.exit(1)
    
    # Parse arguments
    user_prompt = sys.argv[1]
    selected_apps = None
    workflow_type = "template"
    complexity = "medium"
    user_id = None
    output_file = None
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--apps" and i + 1 < len(sys.argv):
            selected_apps = sys.argv[i + 1].split(",")
            i += 2
        elif sys.argv[i] == "--type" and i + 1 < len(sys.argv):
            workflow_type = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--complexity" and i + 1 < len(sys.argv):
            complexity = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--user-id" and i + 1 < len(sys.argv):
            user_id = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--output" and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    
    # Validate workflow type
    if workflow_type not in ["template", "executable", "dag"]:
        print(f"Error: Invalid workflow type '{workflow_type}'. Must be template, executable, or dag.")
        sys.exit(1)
    
    # Validate complexity
    if complexity not in ["simple", "medium", "complex"]:
        print(f"Error: Invalid complexity '{complexity}'. Must be simple, medium, or complex.")
        sys.exit(1)
    
    try:
        # Check for required environment variables
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_api_key:
            print("Error: ANTHROPIC_API_KEY environment variable is required")
            print("Set it with: export ANTHROPIC_API_KEY=your_api_key_here")
            sys.exit(1)
        
        # Create generation request
        request = GenerationRequest(
            user_prompt=user_prompt,
            selected_apps=selected_apps,
            user_id=user_id,
            workflow_type=workflow_type,
            complexity=complexity
        )
        
        print(f"🚀 DSL Generator CLI")
        print(f"   Prompt: {user_prompt}")
        print(f"   Type: {workflow_type}")
        print(f"   Complexity: {complexity}")
        if selected_apps:
            print(f"   Apps: {', '.join(selected_apps)}")
        print()
        
        # Initialize and run the generator
        generator = DSLGeneratorService(anthropic_api_key=anthropic_api_key)
        await generator.initialize()
        
        print("📡 Generating workflow...")
        response = await generator.generate_workflow(request)
        
        if response.success:
            print("✅ Workflow generated successfully!")
            print(f"   Confidence: {response.confidence:.2f}")
            print(f"   Missing fields: {len(response.missing_fields)}")
            
            if response.suggested_apps:
                print(f"   Suggested apps: {', '.join(response.suggested_apps)}")
            
            if response.reasoning:
                print(f"   Reasoning: {response.reasoning}")
            
            # Display missing fields
            if response.missing_fields:
                print("\n📝 Missing fields that need user input:")
                for field in response.missing_fields:
                    print(f"   - {field.field}: {field.prompt}")
                    if field.example:
                        print(f"     Example: {field.example}")
            
            # Display or save the generated DSL
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(response.dsl_template, f, indent=2)
                print(f"\n💾 Generated DSL saved to: {output_file}")
            else:
                print("\n📄 Generated DSL:")
                print(json.dumps(response.dsl_template, indent=2))
                
        else:
            print("❌ Workflow generation failed!")
            print(f"   Error: {response.error_message}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
