# DSL Generator Service - Quick Setup

## 🚀 Quick Start

### 1. Set Environment Variables

```bash
# Required: Anthropic API key for Claude access
export ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Required: Database and Redis for catalog access
export DATABASE_URL=postgresql://user:password@localhost/workflow_automation
export REDIS_URL=redis://localhost:6379

# Optional: Composio API for catalog data
export COMPOSIO_API_KEY=your_composio_api_key_here
```

### 2. Install Dependencies

```bash
# Activate your virtual environment
source venv/bin/activate

# Install httpx for HTTP client functionality
pip install httpx==0.25.2
```

### 3. Test the Service

```bash
# Run simple tests (no external APIs required)
python -m services.dsl_generator.test_simple

# Run examples (requires ANTHROPIC_API_KEY)
python -m services.dsl_generator.example

# Test CLI interface
python -m services.dsl_generator.cli "Send me Slack notifications for important emails"
```

## 🔧 Integration

### FastAPI Integration

The service is already integrated into your planning routes at `/workflows/plan` and `/workflows/generate`.

### Direct Usage

```python
from services.dsl_generator import DSLGeneratorService, GenerationRequest

# Initialize service
generator = DSLGeneratorService()
await generator.initialize()

# Generate workflow
request = GenerationRequest(
    user_prompt="Send me Slack notifications for important emails",
    selected_apps=["gmail", "slack"],
    workflow_type="template"
)

response = await generator.generate_workflow(request)
```

## 📋 What's Included

- **DSLGeneratorService**: Main service class
- **CLI Interface**: Command-line testing tool
- **Example Scripts**: Usage examples
- **FastAPI Routes**: Integration with your API
- **Comprehensive Tests**: Unit and integration tests
- **Full Documentation**: README with examples

## 🎯 Next Steps

1. **Test the service** with the CLI or examples
2. **Integrate with your frontend** using the `/workflows/generate` endpoint
3. **Customize prompts** if needed for your use case
4. **Add more workflow types** or complexity levels as needed

## 🆘 Troubleshooting

- **Missing API Key**: Set `ANTHROPIC_API_KEY` environment variable
- **Catalog Issues**: Ensure your catalog system is populated and accessible
- **Schema Errors**: Verify `core/dsl/schema.json` is valid and accessible

---

For detailed documentation, see [README.md](README.md)
