#!/usr/bin/env python3
"""
Startup script for the Weave API server
"""

import uvicorn
import os
import sys
from pathlib import Path

if __name__ == "__main__":
    # Add the project root to Python path so we can import api modules
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # Set default port if not specified
    port = int(os.getenv("API_PORT", 8001))
    
    # Set default host if not specified
    host = os.getenv("API_HOST", "127.0.0.1")
    
    print(f"Starting Weave API server on {host}:{port}")
    print("API documentation available at http://localhost:8001/docs")
    
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
