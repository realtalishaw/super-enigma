# Enhanced Logging System

The workflow automation engine now includes a comprehensive, enhanced logging system that provides better visibility into application behavior, LLM interactions, and API calls.

## Features

### 🎨 Colored Logging
- **Different colors for different log levels**: DEBUG (gray), INFO (green), WARNING (yellow), ERROR (red), CRITICAL (magenta)
- **Colored timestamps** (cyan) and **logger names** (blue) for better readability
- **Automatic color detection** - colors are only used in terminal output, not in log files

### 📝 Structured Formatting
- **Consistent timestamp format** with millisecond precision
- **Logger name identification** for easy filtering and debugging
- **Multiple format options**: simple, detailed, and JSON formats
- **Configurable log levels** through environment variables

### 🤖 LLM Input/Output Logging
- **Clear visual separators** using dashed lines for LLM interactions
- **Request ID tracking** for correlating requests and responses
- **Prompt and response logging** with truncation for long content
- **Response timing** to monitor LLM performance
- **Error logging** with detailed error information

### 🚀 API Call Dividers
- **Clear start/end markers** using equals signs for API calls
- **Request ID generation** for tracking individual requests
- **Timing information** showing request duration
- **Status tracking** including HTTP status codes
- **Automatic middleware integration** with FastAPI

## Configuration

### Environment Variables

```bash
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Debug mode (overrides LOG_LEVEL to DEBUG)
DEBUG=true

# Log format (simple, detailed, json)
LOG_FORMAT=detailed

# Enable/disable colors (true/false)
ENABLE_COLORS=true

# Optional log file path
LOG_FILE=logs/app.log
```

### Code Configuration

```python
from core.logging_config import setup_logging, get_logger, get_llm_logger

# Set up logging with custom configuration
setup_logging(
    log_level="DEBUG",
    log_format="detailed",
    log_file="logs/app.log",
    enable_colors=True
)

# Get regular logger
logger = get_logger("my_module")

# Get LLM logger for AI interactions
llm_logger = get_llm_logger("my_module")
```

## Usage Examples

### Basic Logging

```python
from core.logging_config import get_logger

logger = get_logger(__name__)

logger.debug("Debug information for developers")
logger.info("General information about application flow")
logger.warning("Warning about potential issues")
logger.error("Error that occurred during execution")
logger.critical("Critical error that may cause system failure")
```

### LLM Request/Response Logging

```python
from core.logging_config import get_llm_logger
import uuid

llm_logger = get_llm_logger(__name__)
request_id = str(uuid.uuid4())[:8]

# Log LLM request
llm_logger.log_llm_request(
    model="claude-3-5-sonnet",
    prompt="Generate a workflow for email automation",
    request_id=request_id
)

# Process request...
response = "Generated workflow content..."

# Log LLM response
llm_logger.log_llm_response(
    model="claude-3-5-sonnet",
    response=response,
    request_id=request_id,
    duration_ms=1250.5
)
```

### API Call Logging

```python
from core.logging_config import get_llm_logger

llm_logger = get_llm_logger(__name__)

# Log API call start
llm_logger.log_api_call_start(
    endpoint="/api/workflows/generate",
    method="POST",
    request_id="abc12345"
)

# Process request...

# Log API call end
llm_logger.log_api_call_end(
    endpoint="/api/workflows/generate",
    method="POST",
    request_id="abc12345",
    duration_ms=1500.0,
    status="success (200)"
)
```

### Error Logging

```python
from core.logging_config import get_llm_logger

llm_logger = get_llm_logger(__name__)

try:
    # Some operation that might fail
    result = risky_operation()
except Exception as e:
    # Log LLM error with request ID
    llm_logger.log_llm_error(
        model="claude-3-5-sonnet",
        error=str(e),
        request_id="abc12345"
    )
    raise
```

## FastAPI Integration

The enhanced logging system automatically integrates with FastAPI through middleware:

```python
from fastapi import FastAPI
from api.middleware import add_logging_middleware

app = FastAPI()

# Add logging middleware for automatic API call logging
add_logging_middleware(app)
```

This middleware automatically:
- Generates unique request IDs
- Logs API call start and end with dividers
- Tracks request timing
- Adds request ID to response headers
- Handles errors gracefully

## Log Output Examples

### Colored Terminal Output

```
2024-01-15 14:30:25.123 - api.middleware - 🚀 API CALL START - POST /api/workflows/generate
📋 Request ID: abc12345
⏰ Timestamp: 2024-01-15 14:30:25.123
================================================================================

2024-01-15 14:30:25.124 - services.dsl_generator - 🤖 LLM REQUEST - claude-3-5-sonnet
📋 Request ID: def67890
📝 Prompt: Generate a workflow for sending emails when new leads are created in CRM...
------------------------------------------------------------

2024-01-15 14:30:26.456 - services.dsl_generator - 🤖 LLM RESPONSE - claude-3-5-sonnet
📋 Request ID: def67890
⏱️  Response Time: 1332.45ms
📄 Response: Here's a workflow for CRM lead email automation...
------------------------------------------------------------

2024-01-15 14:30:26.457 - api.middleware - ✅ API CALL END - POST /api/workflows/generate
📋 Request ID: abc12345
⏰ Timestamp: 2024-01-15 14:30:26.457
⏱️  Duration: 1334.00ms
📊 Status: success (200)
================================================================================
```

### File Output (No Colors)

```
2024-01-15 14:30:25.123 - api.middleware - 🚀 API CALL START - POST /api/workflows/generate
📋 Request ID: abc12345
⏰ Timestamp: 2024-01-15 14:30:25.123
================================================================================

2024-01-15 14:30:25.124 - services.dsl_generator - 🤖 LLM REQUEST - claude-3-5-sonnet
📋 Request ID: def67890
📝 Prompt: Generate a workflow for sending emails when new leads are created in CRM...
------------------------------------------------------------
```

## Testing

The enhanced logging system is automatically active when you start your application. You can see the features in action by:

- Starting the API server and making requests
- Running workflow generation with LLM calls
- Checking the console output for colored logs and dividers

## Migration Guide

### From Old Logging

**Before:**
```python
import logging
logger = logging.getLogger(__name__)
```

**After:**
```python
from core.logging_config import get_logger
logger = get_logger(__name__)
```

### From Basic Logging Setup

**Before:**
```python
logging.basicConfig(level=logging.INFO)
```

**After:**
```python
from core.logging_config import setup_logging
setup_logging(log_level="INFO", enable_colors=True)
```

## Best Practices

1. **Use appropriate log levels**:
   - DEBUG: Detailed information for debugging
   - INFO: General application flow
   - WARNING: Potential issues
   - ERROR: Errors that occurred
   - CRITICAL: System-threatening errors

2. **Include context in log messages**:
   - Request IDs for tracking
   - User IDs for user-specific operations
   - Operation names for clarity

3. **Use LLM logger for AI interactions**:
   - Always log prompts and responses
   - Include timing information
   - Track request IDs for correlation

4. **Configure logging appropriately**:
   - Use DEBUG level in development
   - Use INFO level in production
   - Enable colors in terminal, disable in files

## Troubleshooting

### Colors Not Showing
- Ensure terminal supports ANSI colors
- Check `ENABLE_COLORS` environment variable
- Verify `sys.stdout.isatty()` returns True

### Log Level Not Working
- Check environment variable spelling
- Verify log level is uppercase
- Ensure no conflicting logging configuration

### Middleware Not Working
- Check middleware order in FastAPI app
- Verify middleware is added before other middleware
- Check for import errors in middleware module

## Performance Impact

The enhanced logging system is designed to be lightweight:
- **Minimal overhead** for regular logging operations
- **Efficient color handling** with minimal string operations
- **Smart truncation** for long LLM content
- **Configurable output** to balance detail vs performance

## Future Enhancements

Planned improvements include:
- **Structured logging** with JSON output
- **Log aggregation** for distributed systems
- **Performance metrics** integration
- **Custom log formatters** for specific use cases
- **Log rotation** and archival
