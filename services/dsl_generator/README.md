# DSL Generator Service

A modular workflow DSL generation service using Claude AI to convert natural language prompts into structured workflow definitions. **Now featuring a robust two-step RAG workflow for improved reliability and performance.**

## 🚀 New RAG Implementation

The service has been completely refactored to implement a **Retrieval-Augmented Generation (RAG) workflow** that is much more reliable than the previous approach:

### Two-Step Architecture

1. **Tool Retrieval** - Intelligently selects relevant tools from the catalog
2. **Focused Generation** - Uses Claude with targeted tools to generate workflows

### Key Improvements

- 🎯 **Targeted Tool Selection** - Only relevant tools sent to Claude
- 🚀 **Better Performance** - Smaller prompts, faster generation
- 🔒 **Higher Accuracy** - Claude can't reference non-existent tools
- 🧠 **Intelligent Search** - Groq LLM for smart tool discovery
- 📱 **Graceful Fallbacks** - Works without external LLM APIs

For detailed information about the RAG implementation, see [RAG_IMPLEMENTATION.md](./RAG_IMPLEMENTATION.md).

## Architecture

The service has been refactored into focused, single-responsibility modules with the new RAG workflow:

### Core Components

- **`DSLGeneratorService`** (`generator.py`) - Main orchestrator implementing the RAG workflow
- **`CatalogManager`** (`catalog_manager.py`) - Manages catalog data, caching, and validation
- **`ContextBuilder`** (`context_builder.py`) - Builds generation context from requests and catalog data
- **`PromptBuilder`** (`prompt_builder.py`) - Constructs Claude prompts for different workflow types
- **`AIClient`** (`ai_client.py`) - Handles Claude API calls and AI interaction
- **`ResponseParser`** (`response_parser.py`) - Parses and validates Claude responses
- **`WorkflowValidator`** (`workflow_validator.py`) - Validates generated workflows against schemas

### Data Models

- **`models.py`** - Contains all data structures and Pydantic models

## Key Benefits of Modular Design + RAG

1. **Separation of Concerns** - Each module has a single, well-defined responsibility
2. **Testability** - Individual components can be tested in isolation
3. **Maintainability** - Changes to one area don't affect others
4. **Reusability** - Components can be used independently in other contexts
5. **Clear Dependencies** - Explicit interfaces between components
6. **🎯 Intelligent Tool Selection** - RAG workflow finds only relevant tools
7. **🚀 Performance** - Smaller prompts, faster generation, better accuracy
8. **🔒 Reliability** - Consistent results with robust error handling

## Usage

### Basic Usage (with RAG)

```python
from services.dsl_generator import DSLGeneratorService

# Initialize the service with RAG capabilities
# Groq API key is automatically loaded from .env file
generator = DSLGeneratorService(
    anthropic_api_key="your-claude-key"  # Optional, will use config if not provided
)

# Initialize components
await generator.initialize()

# Generate a workflow using the new RAG workflow
request = GenerationRequest(
    user_prompt="Send a Slack message when a new email arrives",
    selected_apps=["gmail", "slack"],  # Optional - enables strict tool selection
    workflow_type="template",
    complexity="simple"
)

response = await generator.generate_workflow(request)
```

### Advanced Usage (LLM-based tool discovery)

```python
# Let the system intelligently discover relevant tools
request = GenerationRequest(
    user_prompt="Create a workflow that automatically schedules follow-up meetings when important emails arrive",
    workflow_type="template",
    complexity="medium"
    # No selected_apps - system will use Groq to analyze and find relevant tools
)

response = await generator.generate_workflow(request)
```

## Testing the RAG Implementation

The RAG implementation is designed to work with your existing API endpoints. To test:

1. **Set up your .env file** with the required API keys
2. **Start your API server** 
3. **Make requests** to your workflow generation endpoint
4. **Monitor logs** to see the two-step RAG workflow in action

The service will automatically:
- Perform intelligent tool retrieval
- Build focused prompts with relevant tools
- Generate workflows with Claude
- Provide detailed logging for debugging

### Example API Request

```bash
curl -X POST "http://localhost:8000/api/workflows/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "user_prompt": "Send Slack notifications when emails arrive",
    "selected_apps": ["gmail", "slack"],
    "workflow_type": "template",
    "complexity": "medium"
  }'
```

## Module Responsibilities

### DSLGeneratorService (Enhanced with RAG)
- Orchestrates the two-step RAG workflow
- Manages tool retrieval and focused generation
- Provides intelligent tool selection strategies
- Manages component lifecycle
- Provides unified interface for external consumers

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

### Setting up the .env file

You can create the `.env` file manually or use the provided setup script:

#### Option 1: Use the setup script (Recommended)
```bash
# Run the setup script from the project root
python setup_env.py

# Then edit the .env file with your actual API keys
```

#### Option 2: Create manually
Create a `.env` file in the project root with the following configuration:

```bash
# API Keys
GROQ_API_KEY=your_groq_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/workflow_engine

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Application Settings
ENVIRONMENT=development
LOG_LEVEL=INFO
DEBUG=false

# Service URLs
SCHEDULER_URL=http://localhost:8003
COMPOSIO_BASE_URL=https://api.composio.dev
COMPOSIO_API_KEY=your_composio_api_key_here
```

**Note:** 
- The Groq API key is optional. If not provided, the service will fall back to basic tool search.
- Copy this template and replace the placeholder values with your actual API keys and configuration.
- Never commit your actual .env file to version control.

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
