"""
Simple test script for the DSL Generator service.

This script tests basic functionality without requiring external APIs.
"""

import asyncio
import json
import os
import sys
from unittest.mock import Mock, patch

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from services.dsl_generator.generator import DSLGeneratorService
from services.dsl_generator.models import GenerationRequest, GenerationResponse


async def test_service_initialization():
    """Test that the service can be initialized"""
    print("🧪 Testing service initialization...")
    
    try:
        # Mock the catalog service and Redis
        with patch('services.dsl_generator.generator.RedisClientFactory') as mock_redis_factory, \
             patch('services.dsl_generator.generator.DatabaseCatalogService') as mock_catalog_service:
            
            # Mock Redis client
            mock_redis_client = Mock()
            mock_redis_factory.get_client.return_value = mock_redis_client
            
            # Mock catalog service
            mock_catalog_service.return_value = Mock()
            
            # Create service
            generator = DSLGeneratorService()
            
            # Test schema loading
            assert generator.schema_definition is not None
            assert "title" in generator.schema_definition
            
            # Test generation templates
            assert "template" in generator.generation_templates
            assert "executable" in generator.generation_templates
            assert "dag" in generator.generation_templates
            
            print("✅ Service initialization test passed!")
            return True
            
    except Exception as e:
        print(f"❌ Service initialization test failed: {e}")
        return False


async def test_prompt_generation():
    """Test that prompts can be generated correctly"""
    print("🧪 Testing prompt generation...")
    
    try:
        generator = DSLGeneratorService()
        
        # Create a mock context
        from services.dsl_generator.models import GenerationContext, CatalogContext
        
        catalog_context = CatalogContext(
            available_providers=[
                {
                    "name": "Gmail",
                    "slug": "gmail",
                    "description": "Email service"
                }
            ],
            available_triggers=[
                {
                    "name": "Email Received",
                    "toolkit_slug": "gmail",
                    "toolkit_name": "Gmail",
                    "description": "Trigger when email is received"
                }
            ],
            available_actions=[
                {
                    "name": "Send Email",
                    "toolkit_slug": "gmail",
                    "toolkit_name": "Gmail",
                    "description": "Send an email"
                }
            ]
        )
        
        context = GenerationContext(
            request=GenerationRequest(
                user_prompt="Send me a notification when I receive an email",
                workflow_type="template",
                complexity="simple"
            ),
            catalog=catalog_context,
            schema_definition={"title": "Test Schema"}
        )
        
        # Test prompt generation
        prompt = generator._build_claude_prompt(context)
        
        assert "Send me a notification when I receive an email" in prompt
        assert "Template" in prompt
        assert "Simple" in prompt
        assert "Gmail" in prompt
        
        print("✅ Prompt generation test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Prompt generation test failed: {e}")
        return False


async def test_catalog_filtering():
    """Test that catalog filtering works correctly"""
    print("🧪 Testing catalog filtering...")
    
    try:
        generator = DSLGeneratorService()
        
        # Create a mock catalog context
        from services.dsl_generator.models import CatalogContext
        
        catalog_context = CatalogContext(
            available_providers=[
                {"name": "Gmail", "slug": "gmail"},
                {"name": "Slack", "slug": "slack"},
                {"name": "Google Drive", "slug": "googledrive"}
            ],
            available_triggers=[
                {"name": "Email Trigger", "toolkit_slug": "gmail", "toolkit_name": "Gmail"},
                {"name": "Slack Trigger", "toolkit_slug": "slack", "toolkit_name": "Slack"}
            ],
            available_actions=[
                {"name": "Send Email", "toolkit_slug": "gmail", "toolkit_name": "Gmail"},
                {"name": "Send Message", "toolkit_slug": "slack", "toolkit_name": "Slack"}
            ]
        )
        
        # Test filtering by selected apps
        selected_apps = ["gmail", "slack"]
        filtered_context = generator._filter_catalog_by_apps(catalog_context, selected_apps)
        
        # Should only have gmail and slack
        assert len(filtered_context.available_providers) == 2
        assert len(filtered_context.available_triggers) == 2
        assert len(filtered_context.available_actions) == 2
        
        # Should not have googledrive
        provider_slugs = [p["slug"] for p in filtered_context.available_providers]
        assert "googledrive" not in provider_slugs
        assert "gmail" in provider_slugs
        assert "slack" in provider_slugs
        
        print("✅ Catalog filtering test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Catalog filtering test failed: {e}")
        return False


async def test_dsl_validation():
    """Test that DSL validation works correctly"""
    print("🧪 Testing DSL validation...")
    
    try:
        generator = DSLGeneratorService()
        
        # Test valid template
        valid_template = {
            "schema_type": "template",
            "workflow": {"name": "test", "description": "test"},
            "toolkit": {"name": "test", "slug": "test"}
        }
        assert generator._validate_dsl_structure(valid_template) == True
        
        # Test valid executable
        valid_executable = {
            "schema_type": "executable",
            "workflow": {"name": "test", "description": "test"},
            "connections": []
        }
        assert generator._validate_dsl_structure(valid_executable) == True
        
        # Test valid DAG
        valid_dag = {
            "schema_type": "dag",
            "nodes": [],
            "edges": []
        }
        assert generator._validate_dsl_structure(valid_dag) == True
        
        # Test invalid structure
        invalid_dsl = {
            "schema_type": "template",
            "workflow": {"name": "test"}
            # Missing toolkit
        }
        assert generator._validate_dsl_structure(invalid_dsl) == False
        
        # Test unknown schema type
        unknown_schema = {
            "schema_type": "unknown",
            "workflow": {"name": "test"}
        }
        assert generator._validate_dsl_structure(unknown_schema) == False
        
        print("✅ DSL validation test passed!")
        return True
        
    except Exception as e:
        print(f"❌ DSL validation test failed: {e}")
        return False


async def test_missing_field_extraction():
    """Test that missing fields are extracted correctly"""
    print("🧪 Testing missing field extraction...")
    
    try:
        generator = DSLGeneratorService()
        
        # Create a mock context
        from services.dsl_generator.models import GenerationContext, CatalogContext
        
        context = GenerationContext(
            request=GenerationRequest(
                user_prompt="Test workflow",
                workflow_type="template"
            ),
            catalog=CatalogContext(),
            schema_definition={}
        )
        
        # Test template with missing information
        template_with_missing = {
            "schema_type": "template",
            "workflow": {"name": "test"},
            "toolkit": {"name": "test", "slug": "test"},
            "missing_information": [
                {
                    "field": "email_filter",
                    "prompt": "What emails should trigger this?",
                    "type": "string",
                    "required": True
                }
            ]
        }
        
        missing_fields = generator._extract_missing_fields(template_with_missing, context)
        assert len(missing_fields) == 1
        assert missing_fields[0].field == "email_filter"
        assert missing_fields[0].prompt == "What emails should trigger this?"
        assert missing_fields[0].type == "string"
        assert missing_fields[0].required == True
        
        # Test executable with missing connections
        executable_with_missing = {
            "schema_type": "executable",
            "workflow": {"name": "test"},
            "connections": [
                {
                    "toolkit_slug": "gmail",
                    "connection_id": None  # Missing
                }
            ]
        }
        
        missing_fields = generator._extract_missing_fields(executable_with_missing, context)
        assert len(missing_fields) == 1
        assert "gmail" in missing_fields[0].field
        assert "connection_id" in missing_fields[0].field
        
        print("✅ Missing field extraction test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Missing field extraction test failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("🧪 DSL Generator Service - Simple Tests")
    print("=" * 50)
    print()
    
    tests = [
        test_service_initialization,
        test_prompt_generation,
        test_catalog_filtering,
        test_dsl_validation,
        test_missing_field_extraction
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    print()
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
