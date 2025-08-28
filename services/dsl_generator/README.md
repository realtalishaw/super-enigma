# DSL Generator Service

A modular workflow DSL generation service using Claude AI to convert natural language prompts into structured workflow definitions.

## Architecture

The service has been refactored into focused, single-responsibility modules:

### Core Components

- **`DSLGeneratorService`** (`generator.py`) - Main orchestrator that coordinates all components
- **`CatalogManager`** (`catalog_manager.py`) - Manages catalog data, caching, and validation
- **`ContextBuilder`** (`context_builder.py`) - Builds generation context from requests and catalog data
- **`PromptBuilder`** (`prompt_builder.py`) - Constructs Claude prompts for different workflow types
- **`AIClient`** (`ai_client.py`) - Handles Claude API calls and AI interaction
- **`ResponseParser`** (`response_parser.py`) - Parses and validates Claude responses
- **`WorkflowValidator`** (`workflow_validator.py`) - Validates generated workflows against schemas

### Data Models

- **`models.py`** - Contains all data structures and Pydantic models

## Key Benefits of Modular Design

1. **Separation of Concerns** - Each module has a single, well-defined responsibility
2. **Testability** - Individual components can be tested in isolation
3. **Maintainability** - Changes to one area don't affect others
4. **Reusability** - Components can be used independently in other contexts
5. **Clear Dependencies** - Explicit interfaces between components

## Usage

```python
from services.dsl_generator import DSLGeneratorService

# Initialize the service
generator = DSLGeneratorService(anthropic_api_key="your-key")

# Initialize components
await generator.initialize()

# Generate a workflow
request = GenerationRequest(
    user_prompt="Send a Slack message when a new email arrives",
    workflow_type="template",
    complexity="simple"
)

response = await generator.generate_workflow(request)
```

## Module Responsibilities

### DSLGeneratorService
- Orchestrates the entire generation process
- Manages component lifecycle
- Provides unified interface for external consumers
- Delegates specific operations to specialized components

### CatalogManager
- Manages catalog data fetching and caching
- Handles Redis and database connections
- Provides catalog health monitoring
- Extracts and formats catalog data for other components

### ContextBuilder
- Builds generation context from user requests
- Filters catalog data based on selected apps
- Loads schema definitions
- Prepares context for prompt generation

### PromptBuilder
- Constructs Claude prompts for different workflow types
- Includes catalog validation instructions
- Adds complexity-specific guidance
- Handles retry attempts with feedback

### AIClient
- Manages Claude API authentication
- Handles HTTP requests and responses
- Manages timeouts and error handling
- Provides model configuration options

### ResponseParser
- Extracts JSON from Claude responses
- Validates basic DSL structure
- Extracts missing fields and suggested apps
- Calculates confidence scores

### WorkflowValidator
- Validates workflows against schemas
- Runs linting with business rules
- Verifies catalog compliance
- Provides detailed validation feedback

## Configuration

The service can be configured through:

1. **Environment Variables** - API keys and service URLs
2. **Constructor Parameters** - Direct API key injection
3. **Runtime Updates** - Dynamic API key and model changes

## Error Handling

Each module handles errors at the appropriate level:

- **Component Level** - Handles domain-specific errors
- **Service Level** - Provides fallbacks and graceful degradation
- **Interface Level** - Returns structured error responses

## Testing

Each module can be tested independently:

```python
# Test catalog manager
catalog_manager = CatalogManager()
await catalog_manager.initialize()

# Test prompt builder
prompt_builder = PromptBuilder()
prompt = prompt_builder.build_prompt(context, 1, [])

# Test AI client
ai_client = AIClient("test-key")
assert ai_client.is_configured()
```

## Future Enhancements

The modular design makes it easy to:

- Add new AI providers (OpenAI, Gemini, etc.)
- Implement different validation strategies
- Add new workflow types
- Integrate with different catalog systems
- Add caching layers and optimizations
