#!/usr/bin/env python3
"""
Launcher script for the Streamlit evals dashboard.
This script sets up the environment and launches the Streamlit app.
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Launch the Streamlit evals dashboard."""
    
    # Get the directory containing this script
    script_dir = Path(__file__).parent
    streamlit_app = script_dir / "streamlit_app.py"
    
    # Check if the streamlit app exists
    if not streamlit_app.exists():
        print(f"❌ Streamlit app not found at {streamlit_app}")
        sys.exit(1)
    
    # Check if streamlit is installed
    try:
        import streamlit
        print(f"✅ Streamlit {streamlit.__version__} found")
    except ImportError:
        print("❌ Streamlit not installed. Please run: pip install -r requirements.txt")
        sys.exit(1)
    
    # Set environment variables if needed
    env = os.environ.copy()
    
    # Change to the project root directory
    project_root = script_dir.parent
    os.chdir(project_root)
    
    print("🚀 Starting Streamlit evals dashboard...")
    print(f"📁 Working directory: {project_root}")
    print(f"🌐 Dashboard will be available at: http://localhost:8501")
    print("\nPress Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        # Run streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            str(streamlit_app),
            "--server.port", "8501",
            "--server.address", "localhost"
        ], cwd=project_root, env=env)
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Error running Streamlit: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
