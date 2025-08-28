#!/usr/bin/env python3
"""
Test script to verify validator fixes
"""

import asyncio
import json
import sys
import os

# Add the core directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from validator.validator import validate, lint
from validator.models import Stage, ValidateOptions, LintOptions, LintContext
from validator.catalog_validator import catalog_validator

async def test_template_validation():
    """Test template workflow validation"""
    print("Testing template workflow validation...")
    
    # Test the template from the eval artifacts
    template_doc = {
        "schema_type": "template",
        "workflow": {
            "name": "Stripe High-Value Charge Notification",
            "description": "When a Stripe charge succeeds over $100, send a notification to the #sales Slack channel",
            "triggers": [
                {
                    "id": "stripe_charge",
                    "type": "event_based",
                    "toolkit_slug": "stripe",
                    "composio_trigger_slug": "stripe_STRIPE_CHECKOUT_SESSION_COMPLETED_TRIGGER",
                    "requires_auth": True
                }
            ],
            "actions": [
                {
                    "id": "slack_message",
                    "toolkit_slug": "slack",
                    "action_name": "SLACK_POST_MESSAGE",
                    "required_inputs": [
                        {
                            "name": "channel",
                            "source": "#sales",
                            "type": "string",
                            "required": True
                        },
                        {
                            "name": "text",
                            "source": "New charge over $100! Customer: {{ stripe_charge.customer_email }} | Amount: ${{ (stripe_charge.amount_total / 100)|string }}",
                            "type": "string",
                            "required": True
                        }
                    ],
                    "depends_on": ["stripe_charge"],
                    "requires_auth": True
                }
            ],
            "flow_control": {
                "conditions": [
                    {
                        "id": "check_amount",
                        "condition": "{{ stripe_charge.amount_total > 10000 }}",
                        "true_actions": ["slack_message"],
                        "false_actions": []
                    }
                ]
            }
        },
        "missing_information": [],
        "confidence": 80
    }
    
    # Test validation
    validation_result = await validate(Stage.TEMPLATE, template_doc)
    print(f"Validation result: {'PASS' if validation_result.ok else 'FAIL'}")
    if not validation_result.ok:
        print(f"Validation errors: {len(validation_result.errors)}")
        for error in validation_result.errors:
            print(f"  - {error.code}: {error.message}")
    
    # Test linting
    context = LintContext(catalog=None, connections=None)
    lint_result = await lint(Stage.TEMPLATE, template_doc, context)
    print(f"Lint result: {len(lint_result.errors)} errors, {len(lint_result.warnings)} warnings, {len(lint_result.hints)} hints")
    
    if lint_result.errors:
        print("Lint errors:")
        for error in lint_result.errors:
            print(f"  - {error.code}: {error.message}")
    
    if lint_result.warnings:
        print("Lint warnings:")
        for warning in lint_result.warnings:
            print(f"  - {warning.code}: {warning.message}")
    
    return validation_result.ok and len(lint_result.errors) == 0

async def test_catalog_validation():
    """Test catalog validation methods"""
    print("\nTesting catalog validation methods...")
    
    context = LintContext(catalog=None, connections=None)
    
    # Test toolkit validation
    toolkit_exists = await catalog_validator._toolkit_exists("slack", context)
    print(f"Toolkit 'slack' exists: {toolkit_exists}")
    
    toolkit_exists = await catalog_validator._toolkit_exists("unknown_toolkit", context)
    print(f"Toolkit 'unknown_toolkit' exists: {toolkit_exists}")
    
    # Test action validation
    action_exists = await catalog_validator._action_exists("slack", "SLACK_POST_MESSAGE", context)
    print(f"Action 'SLACK_POST_MESSAGE' in 'slack' exists: {action_exists}")
    
    action_exists = await catalog_validator._action_exists("slack", "None", context)
    print(f"Action 'None' in 'slack' exists: {action_exists}")
    
    # Test trigger validation
    trigger_exists = await catalog_validator._trigger_exists("stripe", "stripe_STRIPE_CHECKOUT_SESSION_COMPLETED_TRIGGER", context)
    print(f"Trigger 'stripe_STRIPE_CHECKOUT_SESSION_COMPLETED_TRIGGER' in 'stripe' exists: {trigger_exists}")

async def main():
    """Main test function"""
    print("Testing validator fixes...")
    
    # Test template validation
    template_ok = await test_template_validation()
    
    # Test catalog validation
    await test_catalog_validation()
    
    print(f"\nOverall result: {'PASS' if template_ok else 'FAIL'}")
    return 0 if template_ok else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
