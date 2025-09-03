#!/usr/bin/env python3
"""
Main entry point for the Cron Scheduler service.
"""

import uvicorn
import logging
import os
from pathlib import Path

from core.logging_config import get_logger

logger = get_logger(__name__)


def main():
    """Main entry point."""
    try:
        # Get configuration from environment variables
        host = os.getenv("SCHEDULER_HOST", "0.0.0.0")
        port = int(os.getenv("SCHEDULER_PORT", "8001"))
        reload = os.getenv("SCHEDULER_RELOAD", "false").lower() == "true"
        
        logger.info(f"Starting Cron Scheduler service on {host}:{port}")
        logger.info(f"Reload mode: {reload}")
        
        # Start the FastAPI server
        uvicorn.run(
            "api:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        logger.info("Shutting down Cron Scheduler service")
    except Exception as e:
        logger.error(f"Failed to start Cron Scheduler service: {e}")
        raise


if __name__ == "__main__":
    main()
