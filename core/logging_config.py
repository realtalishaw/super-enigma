"""
Centralized logging configuration for the workflow automation engine.

Features:
- Colored logging with different colors for different log levels
- Structured formatting with timestamps and context
- LLM input/output logging with clear separators
- API call dividers for better readability
- Configurable log levels and output formats
"""

import logging
import sys
import json
import time
from datetime import datetime
from typing import Any, Dict, Optional, Union
from pathlib import Path

# Color codes for terminal output
class Colors:
    """ANSI color codes for terminal output"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log messages"""
    
    COLORS = {
        logging.DEBUG: Colors.GRAY,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.MAGENTA,
    }
    
    def format(self, record):
        # Format the record first to get the asctime
        formatted = super().format(record)
        
        # Add color to the level name
        level_color = self.COLORS.get(record.levelno, Colors.WHITE)
        formatted = formatted.replace(
            record.levelname,
            f"{level_color}{record.levelname}{Colors.RESET}"
        )
        
        # Add color to the timestamp (find and replace the timestamp)
        # The timestamp format is typically at the beginning: "2024-01-15 14:30:25.123"
        import re
        timestamp_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{2,3})'
        formatted = re.sub(timestamp_pattern, f"{Colors.CYAN}\\1{Colors.RESET}", formatted)
        
        # Add color to the logger name if present
        if hasattr(record, 'name') and record.name:
            formatted = formatted.replace(
                f"{record.name} - ",
                f"{Colors.BLUE}{record.name}{Colors.RESET} - "
            )
        
        return formatted

class LLMLogger:
    """Specialized logger for LLM input/output logging"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.divider_length = 80
    
    def log_api_call_start(self, endpoint: str, method: str = "POST", request_id: Optional[str] = None):
        """Log the start of an API call with clear dividers"""
        divider = "=" * self.divider_length
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        self.logger.info(f"\n{Colors.MAGENTA}{divider}{Colors.RESET}")
        self.logger.info(f"{Colors.MAGENTA}🚀 API CALL START - {method} {endpoint}{Colors.RESET}")
        if request_id:
            self.logger.info(f"{Colors.MAGENTA}📋 Request ID: {request_id}{Colors.RESET}")
        self.logger.info(f"{Colors.MAGENTA}⏰ Timestamp: {timestamp}{Colors.RESET}")
        self.logger.info(f"{Colors.MAGENTA}{divider}{Colors.RESET}")
    
    def log_api_call_end(self, endpoint: str, method: str = "POST", request_id: Optional[str] = None, 
                         duration_ms: Optional[float] = None, status: str = "completed"):
        """Log the end of an API call with clear dividers"""
        divider = "=" * self.divider_length
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        self.logger.info(f"\n{Colors.MAGENTA}{divider}{Colors.RESET}")
        self.logger.info(f"{Colors.MAGENTA}✅ API CALL END - {method} {endpoint}{Colors.RESET}")
        if request_id:
            self.logger.info(f"{Colors.MAGENTA}📋 Request ID: {request_id}{Colors.RESET}")
        self.logger.info(f"{Colors.MAGENTA}⏰ Timestamp: {timestamp}{Colors.RESET}")
        if duration_ms:
            self.logger.info(f"{Colors.MAGENTA}⏱️  Duration: {duration_ms:.2f}ms{Colors.RESET}")
        self.logger.info(f"{Colors.MAGENTA}📊 Status: {status}{Colors.RESET}")
        self.logger.info(f"{Colors.MAGENTA}{divider}{Colors.RESET}")
    
    def log_llm_request(self, model: str, prompt: str, request_id: Optional[str] = None):
        """Log LLM request details"""
        divider = "-" * 60
        self.logger.info(f"\n{Colors.CYAN}{divider}{Colors.RESET}")
        self.logger.info(f"{Colors.CYAN}🤖 LLM REQUEST - {model}{Colors.RESET}")
        if request_id:
            self.logger.info(f"{Colors.CYAN}📋 Request ID: {request_id}{Colors.RESET}")
        self.logger.info(f"{Colors.CYAN}📝 Prompt:{Colors.RESET}")
        self.logger.info(f"{Colors.WHITE}{prompt[:500]}{'...' if len(prompt) > 500 else ''}{Colors.RESET}")
        self.logger.info(f"{Colors.CYAN}{divider}{Colors.RESET}")
    
    def log_llm_response(self, model: str, response: str, request_id: Optional[str] = None, 
                        duration_ms: Optional[float] = None):
        """Log LLM response details"""
        divider = "-" * 60
        self.logger.info(f"\n{Colors.CYAN}{divider}{Colors.RESET}")
        self.logger.info(f"{Colors.CYAN}🤖 LLM RESPONSE - {model}{Colors.RESET}")
        if request_id:
            self.logger.info(f"{Colors.CYAN}📋 Request ID: {request_id}{Colors.RESET}")
        if duration_ms:
            self.logger.info(f"{Colors.CYAN}⏱️  Response Time: {duration_ms:.2f}ms{Colors.RESET}")
        self.logger.info(f"{Colors.CYAN}📄 Response:{Colors.RESET}")
        self.logger.info(f"{Colors.WHITE}{response[:500]}{'...' if len(response) > 500 else ''}{Colors.RESET}")
        self.logger.info(f"{Colors.CYAN}{divider}{Colors.RESET}")
    
    def log_llm_error(self, model: str, error: str, request_id: Optional[str] = None):
        """Log LLM error details"""
        divider = "-" * 60
        self.logger.error(f"\n{Colors.RED}{divider}{Colors.RESET}")
        self.logger.error(f"{Colors.RED}❌ LLM ERROR - {model}{Colors.RESET}")
        if request_id:
            self.logger.error(f"{Colors.RED}📋 Request ID: {request_id}{Colors.RESET}")
        self.logger.error(f"{Colors.RED}💥 Error: {error}{Colors.RESET}")
        self.logger.error(f"{Colors.RED}{divider}{Colors.RESET}")

def setup_logging(
    log_level: str = "INFO",
    log_format: str = "detailed",
    log_file: Optional[Union[str, Path]] = None,
    enable_colors: bool = True
) -> logging.Logger:
    """
    Set up centralized logging configuration
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format style ('simple', 'detailed', 'json')
        log_file: Optional file path for logging
        enable_colors: Whether to enable colored output (terminal only)
    
    Returns:
        Configured root logger
    """
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    # Set formatter based on format preference
    if log_format == "simple":
        if enable_colors and sys.stdout.isatty():
            formatter = ColoredFormatter(
                "%(levelname)s - %(message)s"
            )
        else:
            formatter = logging.Formatter(
                "%(levelname)s - %(message)s"
            )
    elif log_format == "json":
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
        )
    else:  # detailed (default)
        if enable_colors and sys.stdout.isatty():
            formatter = ColoredFormatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        # File handler always uses non-colored format
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name"""
    return logging.getLogger(name)

def get_llm_logger(name: str) -> LLMLogger:
    """Get an LLM logger for the specified logger name"""
    return LLMLogger(logging.getLogger(name))

# Global logging configuration
def configure_logging_from_settings():
    """Configure logging based on application settings"""
    try:
        from core.config import settings
        
        # Set up logging based on settings
        log_level = getattr(settings, 'log_level', 'INFO')
        debug_mode = getattr(settings, 'debug', False)
        
        # Override log level if debug mode is enabled
        if debug_mode:
            log_level = 'DEBUG'
        
        # Determine log format based on environment
        log_format = 'detailed'  # Default to detailed format
        
        # Set up logging
        setup_logging(
            log_level=log_level,
            log_format=log_format,
            enable_colors=True
        )
        
        logger = get_logger(__name__)
        logger.info(f"🎨 Logging configured with level: {log_level}, format: {log_format}")
        
    except ImportError:
        # Fallback if settings not available
        setup_logging(log_level='INFO', enable_colors=True)
        logger = get_logger(__name__)
        logger.warning("⚠️  Could not import settings, using default logging configuration")

# Initialize logging when module is imported
configure_logging_from_settings()
