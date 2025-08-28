#!/usr/bin/env python3
"""
Test script to verify catalog system setup.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

async def test_catalog_imports():
    """Test that all catalog components can be imported."""
    print("🔍 Testing catalog system imports...")
    
    try:
        # Test core config import
        from core.config import settings
        print("✅ core.config imported successfully")
        print(f"   Database URL: {settings.database_url}")
        print(f"   Redis URL: {settings.redis_url}")
        
        # Test catalog models import
        from core.catalog.models import Provider, ActionSpec, TriggerSpec
        print("✅ catalog models imported successfully")
        
        # Test catalog fetchers import
        from core.catalog.fetchers import ComposioMCPFetcher, ComposioSDKFetcher
        print("✅ catalog fetchers imported successfully")
        
        # Test catalog services import
        from core.catalog.database_service import DatabaseCatalogService
        from core.catalog.cache import RedisCacheStore
        from core.catalog.redis_client import RedisClientFactory
        print("✅ catalog services imported successfully")
        
        print("🎉 All catalog imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

async def test_environment_setup():
    """Test that required environment variables are set."""
    print("\n🔍 Testing environment setup...")
    
    required_vars = [
        "COMPOSIO_API_KEY",
        "DATABASE_URL", 
        "REDIS_URL"
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var} is set")
        else:
            print(f"❌ {var} is not set")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these variables:")
        for var in missing_vars:
            if var == "COMPOSIO_API_KEY":
                print(f"   export {var}=your_composio_api_key_here")
            elif var == "REDIS_URL":
                print(f"   export {var}=redis://localhost:6379")
        return False
    else:
        print("✅ All required environment variables are set!")
        return True

async def main():
    """Run all tests."""
    print("🚀 Testing catalog system setup...\n")
    
    tests = [
        ("Imports", test_catalog_imports),
        ("Environment", test_environment_setup),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "="*50)
    print("📊 Test Results Summary:")
    print("="*50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:15} {status}")
        if result:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(results)} tests")
    
    if passed == len(results):
        print("🎉 All tests passed! Catalog system is ready to use.")
        print("\nNext steps:")
        print("1. Set up your database and Redis")
        print("2. Run the setup script: python scripts/setup_catalog.py")
    else:
        print("⚠️  Some tests failed. Please fix the issues above before proceeding.")

if __name__ == "__main__":
    asyncio.run(main())
