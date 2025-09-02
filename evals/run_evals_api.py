#!/usr/bin/env python3
"""
Simple API-based evaluation script.
Calls the workflow generation API directly instead of running the full service locally.
"""

import asyncio
import json
import time
import os
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path
import httpx

# Ensure the project root is in the Python path to allow for imports
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Import validator for response validation
from core.validator.validator import lint
from core.validator.models import Stage, LintContext, Catalog, Connections

# --- Helper Classes for the Validator ---

class CatalogCacheAdapter(Catalog):
    """Simple catalog adapter for validation"""
    def __init__(self):
        self._toolkits = {}
    
    async def get_provider_by_slug(self, slug: str) -> Any:
        return self._toolkits.get(slug)

class MockConnections(Connections):
    """Mock connections for validation"""
    async def get_connection(self, connection_id: str):
        return None



# --- API Configuration ---

API_BASE_URL = "http://localhost:8001"  # Default from your .env
SUGGESTIONS_ENDPOINT = f"{API_BASE_URL}/api/suggestions:generate"

# --- Main Evaluation Logic ---

async def call_workflow_api(prompt: str, selected_apps: List[str] = None) -> Dict[str, Any]:
    """Call the workflow generation API endpoint"""
    
    payload = {
        "user_id": "eval_user",  # Required field
        "user_request": prompt,
        "selected_apps": selected_apps or [],
        "num_suggestions": 1
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                SUGGESTIONS_ENDPOINT,
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"error": f"Request failed: {str(e)}"}

async def run_evaluation():
    """Main evaluation function using API calls"""
    print("--- Starting API-Based Workflow Generation Evaluation ---")

    # 1. Load the Golden Dataset of evaluation prompts
    try:
        eval_file_path = Path(__file__).parent / "eval_prompts.json"
        with open(eval_file_path, "r") as f:
            golden_dataset = json.load(f)
        print(f"Loaded {len(golden_dataset)} test cases from {eval_file_path}")
    except FileNotFoundError:
        print(f"ERROR: `eval_prompts.json` not found at {eval_file_path}")
        return
    except json.JSONDecodeError:
        print("ERROR: `eval_prompts.json` contains invalid JSON.")
        return

    # 2. Check if API is running
    print(f"Testing API connection to: {API_BASE_URL}")
    try:
        async with httpx.AsyncClient() as client:
            health_response = await client.get(f"{API_BASE_URL}/health", timeout=5.0)
            if health_response.status_code == 200:
                print("✅ API is running and accessible")
            else:
                print(f"⚠️  API health check returned: {health_response.status_code}")
    except Exception as e:
        print(f"⚠️  Could not connect to API: {e}")
        print("Make sure the API server is running on the configured port")

    results = []

    # 3. Loop Through Each Test Case
    for i, test_case in enumerate(golden_dataset):
        print(f"\n[{i+1}/{len(golden_dataset)}] Running case: {test_case['id']}...")
        
        # 4. Call API and Measure Latency
        start_time = time.time()
        api_response = await call_workflow_api(
            prompt=test_case["prompt"],
            selected_apps=test_case["selected_apps"]
        )
        latency_ms = (time.time() - start_time) * 1000

        # 5. Score the Result
        score = {
            "case_id": test_case["id"],
            "prompt": test_case["prompt"],
            "latency_ms": round(latency_ms),
            "is_valid_schema": False,
            "accuracy_score": 0.0,
            "steps_generated": 0,
            "error_message": None,
            "generated_dsl": None
        }
        
        # Check if API call was successful
        if "error" in api_response:
            score["error_message"] = api_response["error"]
            print(f"Result: FAIL | Latency: {score['latency_ms']}ms | Error: {score['error_message']}")
        else:
            # Extract the generated workflow from API response
            try:
                # The API response structure: {"suggestions": [{"dsl_parametric": {...}}]}
                if "suggestions" in api_response and api_response["suggestions"]:
                    suggestion = api_response["suggestions"][0]  # Get first suggestion
                    
                    # The DSL parametric contains the workflow structure
                    if "dsl_parametric" in suggestion:
                        dsl_parametric = suggestion["dsl_parametric"]
                        generated_workflow = {
                            "workflow": {
                                "name": dsl_parametric.get("name", ""),
                                "triggers": [dsl_parametric.get("trigger", {})],
                                "actions": dsl_parametric.get("actions", [])
                            }
                        }
                    else:
                        generated_workflow = suggestion
                else:
                    generated_workflow = api_response
                
                score["generated_dsl"] = generated_workflow
                
                # Validate the generated workflow
                try:
                    validation_context = LintContext(
                        catalog=CatalogCacheAdapter(), 
                        connections=MockConnections()
                    )
                    validation_result = await lint(Stage.TEMPLATE, generated_workflow, validation_context)
                    score["is_valid_schema"] = len(validation_result.errors) == 0
                    
                    if not score["is_valid_schema"]:
                        score["error_message"] = f"Validation Failed: {[e.message for e in validation_result.errors]}"

                    # Calculate Accuracy Score if valid
                    if score["is_valid_schema"]:
                        try:
                            correct_checks = 0
                            total_checks = 0
                            
                            # For DSL parametric, the structure is different
                            if "suggestions" in api_response and api_response["suggestions"]:
                                suggestion = api_response["suggestions"][0]
                                dsl_parametric = suggestion.get("dsl_parametric", {})
                                
                                # Check trigger
                                total_checks += 1
                                trigger = dsl_parametric.get("trigger", {})
                                if trigger and trigger.get("composio_trigger_slug") == test_case['expected']['trigger_slug']:
                                    correct_checks += 1

                                # Check actions
                                actions = dsl_parametric.get("actions", [])
                                generated_actions = {action.get('action_name', '') for action in actions}
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
                            else:
                                # Fallback to old structure
                                workflow = generated_workflow.get('workflow', generated_workflow)
                                
                                # Check trigger
                                total_checks += 1
                                if workflow.get('triggers') and workflow['triggers'][0].get('composio_trigger_slug') == test_case['expected']['trigger_slug']:
                                    correct_checks += 1

                                # Check actions
                                generated_actions = {action.get('action_name', '') for action in workflow.get('actions', [])}
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
                            print(f"WARNING: Could not score accuracy due to missing key: {e}")
                            score["error_message"] = f"Scoring error: {str(e)}"
                except Exception as e:
                    print(f"WARNING: Could not validate result due to error: {e}")
                    score["error_message"] = f"Validation Error: {str(e)}"
                    
            except Exception as e:
                score["error_message"] = f"Failed to process API response: {str(e)}"
                print(f"Result: FAIL | Latency: {score['latency_ms']}ms | Error: {score['error_message']}")

        results.append(score)

    # 6. Calculate Aggregate Stats
    total_cases = len(results)
    successful_runs = [r for r in results if r["is_valid_schema"]]
    pass_rate = (len(successful_runs) / total_cases) * 100 if total_cases > 0 else 0
    avg_latency = sum(r["latency_ms"] for r in results) / total_cases if total_cases > 0 else 0
    avg_accuracy = sum(r["accuracy_score"] for r in successful_runs) / len(successful_runs) if successful_runs else 0
    
    # 7. Print and Save the final report
    report = {
        "run_timestamp": datetime.now().isoformat(),
        "api_endpoint": SUGGESTIONS_ENDPOINT,
        "summary": {
            "total_cases": total_cases,
            "pass_rate_percent": round(pass_rate, 2),
            "average_latency_ms": round(avg_latency),
            "average_accuracy_on_pass": round(avg_accuracy, 2),
        },
        "results": results
    }

    print("\n--- ✅ API-BASED EVALUATION COMPLETE ---")
    print(json.dumps(report["summary"], indent=2))
    
    # Save report in the evals folder
    evals_dir = Path(__file__).parent
    report_filename = f"api_eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path = evals_dir / report_filename
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nDetailed report saved to: {report_path}")


if __name__ == "__main__":
    # Check if API server is configured
    if not os.getenv("API_PORT"):
        print("⚠️  API_PORT not set in .env, using default: 8001")
    
    print(f"🚀 Starting API-based evaluation...")
    print(f"📡 API Endpoint: {SUGGESTIONS_ENDPOINT}")
    
    asyncio.run(run_evaluation())
