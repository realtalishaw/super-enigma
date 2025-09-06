#!/usr/bin/env python3
"""
Demo script showing how to use the Streamlit evals frontend.
This script demonstrates the key features and provides examples.
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

def print_banner():
    """Print a welcome banner."""
    print("=" * 60)
    print("🚀 WORKFLOW AUTOMATION ENGINE - EVALS FRONTEND DEMO")
    print("=" * 60)
    print()

def check_requirements():
    """Check if all requirements are met."""
    print("🔍 Checking requirements...")
    
    # Check if streamlit is installed
    try:
        import streamlit
        print(f"✅ Streamlit {streamlit.__version__} installed")
    except ImportError:
        print("❌ Streamlit not installed")
        print("   Run: pip install streamlit plotly pandas")
        return False
    
    # Check if plotly is installed
    try:
        import plotly
        print(f"✅ Plotly {plotly.__version__} installed")
    except ImportError:
        print("❌ Plotly not installed")
        return False
    
    # Check if pandas is installed
    try:
        import pandas
        print(f"✅ Pandas {pandas.__version__} installed")
    except ImportError:
        print("❌ Pandas not installed")
        return False
    
    # Check if eval_prompts.json exists
    eval_prompts = Path(__file__).parent / "eval_prompts.json"
    if eval_prompts.exists():
        print(f"✅ Test cases found: {eval_prompts}")
    else:
        print(f"❌ Test cases not found: {eval_prompts}")
        return False
    
    # Check for environment variables
    import os
    from dotenv import load_dotenv
    
    project_root = Path(__file__).parent.parent
    load_dotenv(project_root / ".env")
    
    required_vars = ["ANTHROPIC_API_KEY", "GROQ_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("   Local evaluations will not work, but API-based evaluations might")
    else:
        print("✅ Environment variables configured")
    
    print()
    return True

def show_features():
    """Show the main features of the frontend."""
    print("📋 FRONTEND FEATURES:")
    print()
    print("1. 🚀 Run New Evaluation")
    print("   - Execute evaluations locally or via API")
    print("   - Select specific test cases to run")
    print("   - Real-time progress tracking")
    print("   - Interactive result visualization")
    print()
    print("2. 📊 View Reports")
    print("   - Browse historical evaluation reports")
    print("   - Interactive charts and metrics")
    print("   - Compare performance across runs")
    print("   - Download reports as JSON")
    print()
    print("3. 🔧 Manage Test Cases")
    print("   - View all test cases in a table")
    print("   - Add new test cases")
    print("   - Edit existing test cases")
    print("   - Validate test case structure")
    print()
    print("4. ⚙️  Settings")
    print("   - Environment variable status")
    print("   - API configuration")
    print("   - System information")
    print()

def show_charts():
    """Show what charts are available."""
    print("📈 AVAILABLE CHARTS:")
    print()
    print("• Latency Chart: Response time per test case")
    print("• Accuracy Chart: Accuracy scores across test cases")
    print("• Pass/Fail Distribution: Success rate visualization")
    print("• Summary Metrics: Key performance indicators")
    print()

def launch_frontend():
    """Launch the Streamlit frontend."""
    print("🚀 Launching Streamlit frontend...")
    print()
    print("The dashboard will open in your browser at: http://localhost:8501")
    print("Press Ctrl+C to stop the server")
    print()
    print("-" * 60)
    
    try:
        # Launch the streamlit app
        script_dir = Path(__file__).parent
        streamlit_app = script_dir / "streamlit_app.py"
        project_root = script_dir.parent
        
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            str(streamlit_app),
            "--server.port", "8501",
            "--server.address", "localhost"
        ], cwd=project_root)
        
    except KeyboardInterrupt:
        print("\n👋 Frontend stopped by user")
    except Exception as e:
        print(f"❌ Error launching frontend: {e}")

def show_usage_examples():
    """Show usage examples."""
    print("💡 USAGE EXAMPLES:")
    print()
    print("1. Run a quick evaluation:")
    print("   - Go to 'Run New Evaluation'")
    print("   - Select 'API-based' (if API server is running)")
    print("   - Choose a few test cases")
    print("   - Click 'Run Evaluation'")
    print()
    print("2. View historical results:")
    print("   - Go to 'View Reports'")
    print("   - Select a report from the dropdown")
    print("   - Explore the charts and metrics")
    print()
    print("3. Add a new test case:")
    print("   - Go to 'Manage Test Cases'")
    print("   - Click 'Add New Test Case'")
    print("   - Fill in the required fields")
    print("   - Submit the form")
    print()

def main():
    """Main demo function."""
    print_banner()
    
    if not check_requirements():
        print("❌ Requirements not met. Please install missing dependencies.")
        return
    
    show_features()
    show_charts()
    show_usage_examples()
    
    # Ask if user wants to launch
    print("🎯 Ready to launch the frontend?")
    response = input("Press Enter to launch, or 'q' to quit: ").strip().lower()
    
    if response == 'q':
        print("👋 Goodbye!")
        return
    
    launch_frontend()

if __name__ == "__main__":
    main()
