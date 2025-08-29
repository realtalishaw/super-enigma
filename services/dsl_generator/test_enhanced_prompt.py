#!/usr/bin/env python3
"""
Test script for enhanced prompt generation

This script tests the improved prompt building with more aggressive and explicit instructions.
"""

import json
import logging
from typing import Dict, Any
from generator import DSLGeneratorService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_mock_catalog_context() -> Dict[str, Any]:
    """Create a mock catalog context for testing."""
    return {
        "toolkits": {
            "slack": {
                "name": "Slack",
                "description": "Slack messaging platform",
                "triggers": [
                    {
                        "slug": "SLACK_NEW_MESSAGE",
                        "name": "New Message",
                        "description": "Triggered when a new message is received"
                    }
                ],
                "actions": [
                    {
                        "slug": "SLACK_SEND_MESSAGE",
                        "name": "Send Message",
                        "description": "Send a message to a Slack channel"
                    }
                ]
            },
            "gmail": {
                "name": "Gmail",
                "description": "Gmail email service",
                "triggers": [
                    {
                        "slug": "GMAIL_NEW_EMAIL",
                        "name": "New Email",
                        "description": "Triggered when a new email arrives"
                    }
                ],
                "actions": [
                    {
                        "slug": "GMAIL_SEND_EMAIL",
                        "name": "Send Email",
                        "description": "Send an email"
                    }
                ]
            }
        }
    }


def test_prompt_generation():
    """Test the enhanced prompt generation."""
    logger.info("Testing enhanced prompt generation...")
    
    # Create generator instance
    generator = DSLGeneratorService()
    
    # Create mock request
    class MockRequest:
        def __init__(self, prompt: str):
            self.user_prompt = prompt
    
    request = MockRequest("When I receive a new email in Gmail, send a notification to Slack")
    
    # Create mock catalog context
    catalog_context = create_mock_catalog_context()
    
    # Test prompt generation without previous errors
    prompt = generator._build_robust_claude_prompt(request, catalog_context, [])
    
    logger.info("Generated prompt (first attempt):")
    logger.info("=" * 80)
    logger.info(prompt)
    logger.info("=" * 80)
    
    # Test prompt generation with previous errors
    previous_errors = [
        "Unknown action 'SLACK_RECEIVE_MESSAGE' in toolkit 'slack'",
        "Missing parameter type for 'channel'"
    ]
    
    prompt_with_errors = generator._build_robust_claude_prompt(request, catalog_context, previous_errors)
    
    logger.info("\nGenerated prompt (with previous errors):")
    logger.info("=" * 80)
    logger.info(prompt_with_errors)
    logger.info("=" * 80)
    
    return True


def test_toolkit_mapping():
    """Test the toolkit mapping functionality."""
    logger.info("Testing toolkit mapping...")
    
    generator = DSLGeneratorService()
    catalog_context = create_mock_catalog_context()
    
    toolkit_mapping = generator._create_toolkit_mapping(catalog_context)
    
    logger.info("Toolkit mapping:")
    logger.info(json.dumps(toolkit_mapping, indent=2))
    
    return True


def test_dynamic_example():
    """Test the dynamic example generation."""
    logger.info("Testing dynamic example generation...")
    
    generator = DSLGeneratorService()
    catalog_context = create_mock_catalog_context()
    
    example = generator._generate_dynamic_example(catalog_context)
    
    logger.info("Dynamic example:")
    logger.info("=" * 80)
    logger.info(example)
    logger.info("=" * 80)
    
    return True


def test_workflow_validation():
    """Test the workflow validation functionality."""
    logger.info("Testing workflow validation...")
    
    generator = DSLGeneratorService()
    catalog_context = create_mock_catalog_context()
    
    # Test valid workflow
    valid_workflow = {
        "workflow": {
            "triggers": [
                {
                    "toolkit_slug": "gmail",
                    "composio_trigger_slug": "GMAIL_NEW_EMAIL"
                }
            ],
            "actions": [
                {
                    "toolkit_slug": "slack",
                    "action_name": "SLACK_SEND_MESSAGE",
                    "required_inputs": [
                        {"name": "channel", "source": "{{inputs.channel}}", "type": "string"}
                    ]
                }
            ]
        }
    }
    
    errors = generator._validate_generated_workflow(valid_workflow, catalog_context)
    logger.info(f"Valid workflow validation errors: {errors}")
    
    # Test invalid workflow
    invalid_workflow = {
        "workflow": {
            "triggers": [
                {
                    "toolkit_slug": "gmail",
                    "composio_trigger_slug": "INVALID_TRIGGER"
                }
            ],
            "actions": [
                {
                    "toolkit_slug": "slack",
                    "action_name": "INVALID_ACTION",
                    "required_inputs": [
                        {"name": "channel", "source": "{{inputs.channel}}"}]  # Missing type
                    ]
                }
            ]
        }
    }
    
    errors = generator._validate_generated_workflow(invalid_workflow, catalog_context)
    logger.info(f"Invalid workflow validation errors: {errors}")
    
    return True


def main():
    """Run all tests."""
    logger.info("Starting enhanced prompt generation tests...")
    
    try:
        # Test 1: Prompt generation
        test_prompt_generation()
        
        # Test 2: Toolkit mapping
        test_toolkit_mapping()
        
        # Test 3: Dynamic example generation
        test_dynamic_example()
        
        # Test 4: Workflow validation
        test_workflow_validation()
        
        logger.info("All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    main()
