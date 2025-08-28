#!/usr/bin/env python3
"""
Startup script for the Weave UI application
"""

import uvicorn
import os

if __name__ == "__main__":
    # Set default port if not specified
    port = int(os.getenv("PORT", 8000))
    
    # Set default host if not specified
    host = os.getenv("HOST", "127.0.0.1")
    
    print(f"Starting Weave UI on {host}:{port}")
    print("Open your browser to http://localhost:8000")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
