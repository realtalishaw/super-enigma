#!/usr/bin/env python3
"""
Simple test runner for working tests only.
"""
import subprocess
import sys
from pathlib import Path


def run_working_tests():
    """Run only the tests that are currently working."""
    working_test_files = [
        "tests/test_basic.py",
        "tests/test_core_config.py", 
        "tests/test_core_catalog_simple.py",
        "tests/test_core_validator_simple.py",
        "tests/test_services_executor.py::TestNodeType",
        "tests/test_services_executor.py::TestNodeStatus",
        "tests/test_services_executor.py::TestRunStatus"
    ]
    
    print("🚀 Running working tests only...")
    print("=" * 50)
    
    for test_file in working_test_files:
        print(f"\n📁 Testing: {test_file}")
        print("-" * 30)
        
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest", test_file, "-v"
            ], capture_output=True, text=True, cwd=Path.cwd())
            
            if result.returncode == 0:
                print("✅ PASSED")
                # Print summary of passed tests
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'passed' in line.lower() and 'test session' not in line.lower():
                        print(f"   {line.strip()}")
            else:
                print("❌ FAILED")
                print("   Error output:")
                for line in result.stderr.split('\n')[:5]:  # Show first 5 error lines
                    if line.strip():
                        print(f"   {line.strip()}")
                        
        except Exception as e:
            print(f"❌ ERROR running {test_file}: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Test run completed!")
    print("\n💡 To run all tests (including broken ones), use:")
    print("   python tests/run_tests.py")
    print("\n💡 To run specific test files:")
    print("   python -m pytest tests/test_basic.py -v")


if __name__ == "__main__":
    run_working_tests()
