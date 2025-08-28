#!/usr/bin/env python3
"""
Test script for single action workflow execution

This script demonstrates how to:
1. Define a simple executable DAG with one action
2. Set up trigger data (event payload)
3. Execute the workflow using the executor
4. Capture and display all logs and responses

SETUP:
1. Create a .env file in this directory with:
   COMPOSIO_BASE_URL=your_composio_url
   COMPOSIO_API_KEY=your_composio_api_key
2. Install python-dotenv: pip install python-dotenv
3. Run: python test_single_action_workflow.py
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any
from dotenv import load_dotenv
from composio import Composio

# Load environment variables from .env file
load_dotenv()

# Add the services/executor directory to the path so we can import the executor
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'services', 'executor'))

from executor import execute_workflow_async

# Configure logging to capture everything
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('workflow_test.log')
    ]
)

# Capture all logs
logger = logging.getLogger(__name__)

def extract_trigger_data(trigger_data: Dict[str, Any], dag: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract data from trigger response using the DAG's data mapping schema.
    This makes it universal for any trigger type, not hardcoded for specific triggers.
    
    Args:
        trigger_data: Raw trigger data from Composio
        dag: The workflow DAG containing the data mapping schema
        
    Returns:
        Mapped data that the executor can access as inputs.field_name
    """
    # Find the trigger node to get the data mapping
    trigger_node = None
    for node in dag["nodes"]:
        if node["type"] == "trigger":
            trigger_node = node
            break
    
    if not trigger_node or "data_mapping" not in trigger_node["data"]:
        logger.warning("No data mapping found in trigger node, using raw trigger data")
        return trigger_data
    
    data_mapping = trigger_node["data"]["data_mapping"]
    mapped_data = {}
    
    # Apply the data mapping to extract fields
    for output_key, source_path in data_mapping.items():
        try:
            # Navigate the source path (e.g., "payload.sender" -> trigger_data["payload"]["sender"])
            value = trigger_data
            for path_part in source_path.split("."):
                value = value[path_part]
            mapped_data[output_key] = value
        except (KeyError, TypeError) as e:
            logger.warning(f"Could not extract {output_key} from path {source_path}: {e}")
            mapped_data[output_key] = None
    
    logger.info(f"Data mapping applied successfully")
    return mapped_data

async def test_single_action_workflow():
    """Test a simple workflow with one action node using REAL Composio triggers"""
    
    global executable_dag
    
    # ============================================================================
    # SECTION 1: EXECUTABLE DAG DEFINITION
    # ============================================================================
    # Define a simple DAG with one trigger and one action
    # This represents: trigger -> action (e.g., email received -> reply to email)
    
    executable_dag = {
        "nodes": [
            {
                "id": "trigger_1",
                "type": "trigger",
                "data": {
                    "event_type": "gmail_email_received",
                    "description": "Trigger when Gmail email is received",
                    "data_mapping": {
                        "sender": "payload.sender",
                        "subject": "payload.subject",
                        "thread_id": "payload.thread_id",
                        "message_text": "payload.message_text",
                        "to": "payload.to",
                        "message_id": "payload.id"
                    }
                }
            },
            {
                "id": "filter_1",
                "type": "gateway_if",
                "data": {
                    "description": "Filter emails from talisha@alcemi.dev",
                    "branches": [
                        {
                            "expr": "'talisha@alcemi.dev' in inputs.sender",
                            "to": "action_1"
                        }
                    ],
                    "else_to": "end_1"
                }
            },
            {
                "id": "action_1", 
                "type": "action",
                "data": {
                    "tool": "gmail",
                    "action": "GMAIL_SEND_EMAIL",
                    "connection_id": "ca_O9UpbnmgnLez",
                    "requires_auth": True,
                    "input_template": {
                        # Required parameters - explicitly defined for clarity
                        "body": "This is a test reply from Composio workflow automation!",  # Static value
                        # Dynamic value - will be parsed from trigger input
                        "recipient_email": "{{ inputs.sender | extract_email }}",
                        
                        # Optional parameters with defaults
                        "subject": "Re: {{ inputs.subject }}",  # Dynamic from trigger
                        "is_html": False,  # Static boolean
                        "cc": [],  # Static empty list
                        "bcc": [],  # Static empty list
                        "extra_recipients": [],  # Static empty list
                        "attachment": None,  # Static None
                        "user_id": "me"  # Static string
                    },
                    "output_vars": {
                        "message_id": "id",
                        "thread_id": "threadId",
                        "status": "labelIds"
                    },
                    "retry": {
                        "retries": 2,
                        "backoff": "linear", 
                        "delay_ms": 1000
                    },
                    "timeout_ms": 30000
                }
            },
            {
                "id": "end_1",
                "type": "gateway_if",
                "data": {
                    "description": "End workflow - email filtered out",
                    "branches": [],
                    "else_to": None
                }
            }
        ],
        "edges": [
            {
                "source": "trigger_1",
                "target": "filter_1",
                "condition": None
            },
            {
                "source": "filter_1",
                "target": "action_1",
                "condition": "talisha@alcemi.dev in inputs.sender"
            },
            {
                "source": "filter_1",
                "target": "end_1",
                "condition": "else"
            }
        ]
    }
    
    logger.info("=== EXECUTABLE DAG DEFINITION ===")
    logger.info(json.dumps(executable_dag, indent=2))
    
    # ============================================================================
    # SECTION 2: REAL COMPOSIO TRIGGER SUBSCRIPTION
    # ============================================================================
    # Subscribe to real Composio triggers - any tool, any event
    
    try:
        logger.info("=== REAL COMPOSIO TRIGGER SUBSCRIPTION ===")
        logger.info("Setting up Composio client and trigger subscription...")
        
        # Get Composio credentials from environment
        composio_base_url = os.getenv("COMPOSIO_BASE_URL")
        composio_api_key = os.getenv("COMPOSIO_API_KEY")
        
        if not composio_base_url or not composio_api_key:
            logger.error("Missing Composio credentials!")
            logger.error("Please create a .env file in this directory with:")
            logger.error("COMPOSIO_BASE_URL=your_composio_url")
            logger.error("COMPOSIO_API_KEY=your_composio_api_key")
            return
        
        logger.info(f"Composio Base URL: {composio_base_url}")
        logger.info(f"Composio API Key: {composio_api_key[:8]}...")
        
        # Initialize Composio client
        try:
            logger.info("🔧 Initializing Composio client...")
            composio = Composio(
                api_key=composio_api_key,
                base_url=composio_base_url
            )
            logger.info("✅ Composio client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Composio client: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"API Key (first 8 chars): {composio_api_key[:8] if composio_api_key else 'None'}")
            logger.error(f"Base URL: {composio_base_url}")
            raise
        
        # Subscribe to triggers - any tool, any event
        user_id = "misstalishawhite@gmail.com"  # Replace with actual user ID
        # Extract toolkit from the DAG for trigger subscription
        # Look for the first action node to determine the toolkit
        toolkit = None
        for node in executable_dag["nodes"]:
            if node["type"] == "action" and "tool" in node["data"]:
                toolkit = node["data"]["tool"].upper()
                break
        
        if not toolkit:
            logger.warning("No toolkit found in DAG, subscribing to all triggers")
            toolkit = None
        
        logger.info(f"Subscribing to triggers for toolkit: {toolkit or 'ALL'}")
        logger.info(f"Subscribing to triggers for user: {user_id}")
        
        try:
            logger.info("🔧 Creating trigger subscription...")
            subscription = composio.triggers.subscribe()
            logger.info("✅ Trigger subscription created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create trigger subscription: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"User ID: {user_id}")
            logger.error(f"Toolkit: {toolkit}")
            logger.error(f"Composio client: {composio}")
            raise
        
        # Universal trigger handler - works with any trigger type
        @subscription.handle(user_id=user_id, toolkit=toolkit)
        def handle_any_trigger(data):
            logger.info("🎯 TRIGGER FIRED!")
            logger.info(f"Trigger data: {json.dumps(data, indent=2)}")
            
            # Save the real trigger data
            with open('real_trigger_response.json', 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info("Real trigger data saved to: real_trigger_response.json")
            
            # Execute the workflow with real trigger data
            # Note: This runs in the trigger handler context, not the main async context
            try:
                # Run the workflow execution synchronously
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(execute_workflow_with_trigger(data))
                loop.close()
                logger.info("✅ Workflow execution completed from trigger handler")
            except Exception as e:
                logger.error(f"❌ Workflow execution failed in trigger handler: {e}")
        
        logger.info("✅ Trigger handler registered successfully")
        logger.info("Waiting for triggers to fire... (Press Ctrl+C to stop)")
        
        # The subscription is now active and listening for triggers
        # (Composio SDK handles the WebSocket connection automatically)
        logger.info("✅ Trigger subscription is now active and listening for events")
        logger.info("Waiting for triggers to fire... (Press Ctrl+C to stop)")
        
        # Keep the script running to receive triggers
        # This is a simple way to keep the process alive
        while True:
            await asyncio.sleep(1)
        
    except Exception as e:
        logger.error(f"❌ Trigger subscription failed: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        raise
    
    # ============================================================================
    # SECTION 3: WORKFLOW EXECUTION FUNCTION
    # ============================================================================
    # This function will be called when triggers fire
    
async def execute_workflow_with_trigger(trigger_data):
    """Execute the workflow when a real trigger fires"""
    try:
        logger.info("=== EXECUTING WORKFLOW WITH REAL TRIGGER ===")
        logger.info("Starting workflow execution...")
        
        # Get Composio credentials from environment
        composio_base_url = os.getenv("COMPOSIO_BASE_URL")
        composio_api_key = os.getenv("COMPOSIO_API_KEY")
        
        # Extract data from trigger response using the DAG's data mapping schema
        # This makes it universal for any trigger type, not hardcoded for Gmail
        mapped_data = extract_trigger_data(trigger_data, executable_dag)
        
        logger.info(f"Extracted trigger data for executor: {json.dumps(mapped_data, indent=2)}")
        
        # Execute the workflow with properly mapped trigger data
        run_id = await execute_workflow_async(
            dag=executable_dag,
            event_payload=mapped_data,  # ← Now the executor can access inputs.sender, etc.
            user_id="misstalishawhite@gmail.com",
            workflow_id="test_single_action_001",
            version="1.0",
            composio_base_url=composio_base_url,
            composio_api_key=composio_api_key
        )
        
        logger.info(f"✅ Workflow execution completed successfully!")
        logger.info(f"Run ID: {run_id}")
        
        # Save execution result
        execution_result = {
            "run_id": run_id,
            "status": "success",
            "workflow_id": "test_single_action_001",
            "user_id": "test_user_123",
            "timestamp": "2024-01-15T10:30:00Z",
            "trigger_data": trigger_data
        }
        
        with open('execution_result.json', 'w') as f:
            json.dump(execution_result, f, indent=2)
        
        logger.info("Execution result saved to: execution_result.json")
        
    except Exception as e:
        logger.error(f"❌ Workflow execution failed: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        
        # Save error details
        error_result = {
            "error": str(e),
            "error_type": type(e).__name__,
            "workflow_id": "test_single_action_001",
            "timestamp": "2024-01-15T10:30:00Z",
            "trigger_data": trigger_data
        }
        
        with open('execution_error.json', 'w') as f:
            json.dump(error_result, f, indent=2)
        
        logger.info("Error details saved to: execution_error.json")
        raise
    
    # ============================================================================
    # SECTION 4: LOGS AND RESPONSES SUMMARY
    # ============================================================================
    # Print summary of all captured information
    
    logger.info("=== EXECUTION SUMMARY ===")
    logger.info("Files created:")
    logger.info("- real_trigger_response.json: Real trigger data from Composio")
    logger.info("- execution_result.json: Successful execution details")
    logger.info("- workflow_test.log: Complete execution logs")
    logger.info("- execution_error.json: Error details (if execution failed)")
    
    logger.info("=== NEXT STEPS ===")
    logger.info("1. Check the log files for detailed execution information")
    logger.info("2. Verify the real trigger data matches your expected format")
    logger.info("3. Review the DAG structure for your specific use case")
    logger.info("4. Modify the action node configuration as needed")
    logger.info("5. The script is now listening for real triggers - trigger some events!")

def main():
    """Main function to run the test"""
    logger.info("🚀 Starting Single Action Workflow Test with REAL Composio Triggers")
    logger.info("=" * 50)
    
    try:
        # Run the async workflow test
        asyncio.run(test_single_action_workflow())
    except KeyboardInterrupt:
        logger.info("=" * 50)
        logger.info("🛑 Test stopped by user (Ctrl+C)")
        logger.info("✅ Test completed successfully!")
    except Exception as e:
        logger.error("=" * 50)
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
