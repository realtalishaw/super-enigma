#!/usr/bin/env python3
"""
Evaluation script for testing the workflow generation system.
Loads configuration from .env file in the project root.
"""

import asyncio
import json
import time
import os
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

# Ensure the project root is in the Python path to allow for imports
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Import your project's components
from services.dsl_generator.generator import DSLGeneratorService
from services.dsl_generator.models import GenerationRequest
from core.validator.validator import lint
from core.validator.models import Stage, LintContext, Catalog, Connections

# --- Helper Classes for the Validator ---

class CatalogCacheAdapter(Catalog):
    """
    Adapter to make the in-memory catalog cache compatible with the 
    validator's expected interface.
    """
    def __init__(self, pruned_catalog: Dict[str, Any]):
        self._toolkits = pruned_catalog.get("toolkits", {})
        print(f"DEBUG: CatalogCacheAdapter initialized with toolkits: {list(self._toolkits.keys())}")

    async def get_provider_by_slug(self, slug: str) -> Any:
        # The validator calls this to check if a toolkit exists
        return self._toolkits.get(slug)

class MockConnections(Connections):
    """A mock connection service since templates don't have concrete connection_ids."""
    async def get_connection(self, connection_id: str):
        return None

# --- Main Evaluation Logic ---

async def run_evaluation():
    """
    Main evaluation function. Loads prompts, runs the generator, scores the results,
    and saves a detailed report.
    """
    print("--- Starting Workflow Generation Evaluation ---")

    # 1. Load the Golden Dataset of evaluation prompts
    try:
        eval_file_path = Path(__file__).parent / "eval_prompts.json"
        with open(eval_file_path, "r") as f:
            golden_dataset = json.load(f)
        print(f"Loaded {len(golden_dataset)} test cases from {eval_file_path}")
    except FileNotFoundError:
        print(f"ERROR: `eval_prompts.json` not found at {eval_file_path}. Please create it before running evaluations.")
        return
    except json.JSONDecodeError:
        print("ERROR: `eval_prompts.json` contains invalid JSON.")
        return

    # 2. Initialize the DSL Generator Service
    generator = DSLGeneratorService()
    await generator.initialize()

    # 3. Initialize cache service and set catalog
    try:
        from api.cache_service import global_cache_service
        await global_cache_service.initialize()
        generator.set_global_cache(global_cache_service.get_catalog_cache())
        print("✅ Cache service initialized successfully")
    except Exception as e:
        print(f"⚠️  Cache service initialization failed: {e}")
        print("Continuing with limited functionality...")

    results = []

    # 4. Loop Through Each Test Case
    for i, test_case in enumerate(golden_dataset):
        print(f"\n[{i+1}/{len(golden_dataset)}] Running case: {test_case['id']}...")
        
        request = GenerationRequest(
            user_prompt=test_case["prompt"],
            selected_apps=test_case["selected_apps"]
        )

        # 5. Measure Latency and Generate Workflow
        start_time = time.time()
        response = await generator.generate_workflow(request)
        latency_ms = (time.time() - start_time) * 1000

        # 6. Score the Result
        score = {
            "case_id": test_case["id"],
            "prompt": test_case["prompt"],
            "latency_ms": round(latency_ms),
            "is_valid_schema": False,
            "accuracy_score": 0.0,
            "steps_generated": 0,
            "error_message": response.error_message,
            "generated_dsl": response.dsl_template
        }

        if response.success and response.dsl_template:
            # A. Validate the output using your real validator
            try:
                catalog_data = await generator.catalog_manager.get_catalog_data()
                validation_context = LintContext(catalog=CatalogCacheAdapter(catalog_data), connections=MockConnections())
                validation_result = await lint(Stage.TEMPLATE, response.dsl_template, validation_context)
                score["is_valid_schema"] = len(validation_result.errors) == 0
                
                if not score["is_valid_schema"]:
                     score["error_message"] = f"Validation Failed: {[e.message for e in validation_result.errors]}"

                # B. Calculate Accuracy Score if valid
                if score["is_valid_schema"]:
                    try:
                        correct_checks = 0
                        total_checks = 0
                        workflow = response.dsl_template['workflow']
                        
                        # Check trigger
                        total_checks += 1
                        if workflow['triggers'] and workflow['triggers'][0]['composio_trigger_slug'] == test_case['expected']['trigger_slug']:
                            correct_checks += 1

                        # Check actions
                        generated_actions = {action['action_name'] for action in workflow.get('actions', [])}
                        score["steps_generated"] = len(generated_actions)
                        total_checks += 1
                        if all(action in generated_actions for action in test_case['expected']['action_slugs']):
                            correct_checks += 1
                        
                        # Check min steps
                        total_checks += 1
                        if score["steps_generated"] >= test_case['expected']['min_steps']:
                            correct_checks += 1
                        
                        score["accuracy_score"] = round(correct_checks / total_checks, 2)
                        print(f"Result: PASS | Latency: {score['latency_ms']}ms | Accuracy: {score['accuracy_score']}")
                    except KeyError as e:
                        print(f"WARNING: Could not score accuracy due to missing key in generated DSL: {e}")
            except Exception as e:
                print(f"WARNING: Could not validate result due to error: {e}")
                score["error_message"] = f"Validation Error: {str(e)}"
        else:
            print(f"Result: FAIL | Latency: {score['latency_ms']}ms | Error: {score['error_message']}")

        results.append(score)

    # Test multiple generation functionality
    print("\n--- Testing Multiple Generation Functionality ---")
    try:
        test_request = GenerationRequest(
            user_prompt="Send a notification when a new email arrives",
            selected_apps=["gmail"]
        )
        
        print("Testing generation of 3 workflows in parallel...")
        start_time = time.time()
        multiple_responses = await generator.generate_multiple_workflows(test_request, 3)
        multi_latency_ms = (time.time() - start_time) * 1000
        
        print(f"✅ Multiple generation completed in {multi_latency_ms:.0f}ms")
        print(f"✅ Generated {len(multiple_responses)} workflows")
        
        for i, response in enumerate(multiple_responses):
            status = "SUCCESS" if response.success else "FAILED"
            print(f"  Workflow {i+1}: {status}")
            if response.success:
                print(f"    - Title: {response.dsl_template.get('workflow', {}).get('name', 'Unknown')}")
                print(f"    - Confidence: {response.confidence:.2f}")
            else:
                print(f"    - Error: {response.error_message}")
                
    except Exception as e:
        print(f"❌ Multiple generation test failed: {e}")

    # 7. Calculate Aggregate Stats for the entire run
    total_cases = len(results)
    successful_runs = [r for r in results if r["is_valid_schema"]]
    pass_rate = (len(successful_runs) / total_cases) * 100 if total_cases > 0 else 0
    avg_latency = sum(r["latency_ms"] for r in results) / total_cases if total_cases > 0 else 0
    avg_accuracy = sum(r["accuracy_score"] for r in successful_runs) / len(successful_runs) if successful_runs else 0

    # 8. Print and Save the final report
    report = {
        "run_timestamp": datetime.now().isoformat(),
        "summary": {
            "total_cases": total_cases,
            "pass_rate_percent": round(pass_rate, 2),
            "average_latency_ms": round(avg_latency),
            "average_accuracy_on_pass": round(avg_accuracy, 2),
        },
        "results": results
    }

    print("\n--- ✅ EVALUATION COMPLETE ---")
    print(json.dumps(report["summary"], indent=2))
    
    report_filename = f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_filename, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nDetailed report saved to: {report_filename}")


if __name__ == "__main__":
    # Check required environment variables
    required_vars = ["ANTHROPIC_API_KEY", "GROQ_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   {var}")
        print(f"\nPlease check your .env file at: {project_root / '.env'}")
        print("Or set the variables manually:")
        for var in missing_vars:
            print(f"   export {var}='your_key_here'")
        exit(1)
    
    print("✅ Environment variables loaded successfully")
    print("🚀 Starting evaluation...")
    
    asyncio.run(run_evaluation())