"""
FastAPI middleware for enhanced logging with API call dividers and timing.

This middleware:
- Adds unique request IDs to all requests
- Logs API call start and end with clear dividers
- Tracks request timing
- Integrates with the centralized logging system
"""

import time
import uuid
import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.logging_config import get_logger, get_llm_logger

logger = get_logger(__name__)
llm_logger = get_llm_logger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for enhanced request logging with dividers and timing"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Log API call start
        endpoint = f"{request.method} {request.url.path}"
        llm_logger.log_api_call_start(
            endpoint=endpoint,
            method=request.method,
            request_id=request_id
        )
        
        # Record start time
        start_time = time.time()
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log API call end
            status = "completed"
            if hasattr(response, 'status_code'):
                if response.status_code >= 400:
                    status = f"error ({response.status_code})"
                else:
                    status = f"success ({response.status_code})"
            
            llm_logger.log_api_call_end(
                endpoint=endpoint,
                method=request.method,
                request_id=request_id,
                duration_ms=duration_ms,
                status=status
            )
            
            # Add request ID to response headers for debugging
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
            
            return response
            
        except Exception as e:
            # Calculate duration for failed requests
            duration_ms = (time.time() - start_time) * 1000
            
            # Log API call end with error
            llm_logger.log_api_call_end(
                endpoint=endpoint,
                method=request.method,
                request_id=request_id,
                duration_ms=duration_ms,
                status=f"error: {str(e)}"
            )
            
            # Re-raise the exception
            raise

def add_logging_middleware(app):
    """Add logging middleware to FastAPI app"""
    app.add_middleware(LoggingMiddleware)
    logger.info("🔧 Logging middleware added to FastAPI app")
