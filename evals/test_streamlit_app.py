#!/usr/bin/env python3
"""
Test script to verify the Streamlit app can be imported and basic functions work.
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    
    try:
        import streamlit
        print(f"✅ Streamlit {streamlit.__version__}")
    except ImportError as e:
        print(f"❌ Streamlit import failed: {e}")
        return False
    
    try:
        import plotly
        print(f"✅ Plotly {plotly.__version__}")
    except ImportError as e:
        print(f"❌ Plotly import failed: {e}")
        return False
    
    try:
        import pandas
        print(f"✅ Pandas {pandas.__version__}")
    except ImportError as e:
        print(f"❌ Pandas import failed: {e}")
        return False
    
    return True

def test_eval_prompts():
    """Test that eval prompts can be loaded."""
    print("\nTesting eval prompts loading...")
    
    try:
        eval_file_path = Path(__file__).parent / "eval_prompts.json"
        with open(eval_file_path, "r") as f:
            prompts = json.load(f)
        
        print(f"✅ Loaded {len(prompts)} test cases")
        
        # Check structure of first prompt
        if prompts:
            first_prompt = prompts[0]
            required_keys = ["id", "prompt", "selected_apps", "expected"]
            missing_keys = [key for key in required_keys if key not in first_prompt]
            
            if missing_keys:
                print(f"❌ Missing keys in first prompt: {missing_keys}")
                return False
            else:
                print("✅ Prompt structure looks good")
        
        return True
        
    except FileNotFoundError:
        print("❌ eval_prompts.json not found")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        return False

def test_eval_reports():
    """Test that eval reports can be loaded."""
    print("\nTesting eval reports loading...")
    
    try:
        evals_dir = Path(__file__).parent
        report_files = list(evals_dir.glob("*eval_report*.json"))
        
        print(f"✅ Found {len(report_files)} report files")
        
        if report_files:
            # Try to load the first report
            with open(report_files[0], "r") as f:
                report = json.load(f)
            
            required_keys = ["run_timestamp", "summary", "results"]
            missing_keys = [key for key in required_keys if key not in report]
            
            if missing_keys:
                print(f"❌ Missing keys in report: {missing_keys}")
                return False
            else:
                print("✅ Report structure looks good")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading reports: {e}")
        return False

def test_streamlit_app_functions():
    """Test that the Streamlit app functions can be imported."""
    print("\nTesting Streamlit app functions...")
    
    try:
        # Import the app module
        from streamlit_app import (
            load_eval_prompts,
            load_eval_reports,
            display_summary_metrics,
            create_latency_chart,
            create_accuracy_chart,
            create_pass_fail_chart
        )
        print("✅ Streamlit app functions imported successfully")
        
        # Test loading functions
        prompts = load_eval_prompts()
        if prompts:
            print(f"✅ load_eval_prompts() works: {len(prompts)} prompts")
        else:
            print("⚠️  load_eval_prompts() returned empty list")
        
        reports = load_eval_reports()
        print(f"✅ load_eval_reports() works: {len(reports)} reports")
        
        return True
        
    except ImportError as e:
        print(f"❌ Streamlit app import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing app functions: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 TESTING STREAMLIT EVALS FRONTEND")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_eval_prompts,
        test_eval_reports,
        test_streamlit_app_functions
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 TEST RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The frontend should work correctly.")
        print("\nTo launch the frontend, run:")
        print("  python evals/run_streamlit.py")
        print("  or")
        print("  python evals/demo_frontend.py")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
