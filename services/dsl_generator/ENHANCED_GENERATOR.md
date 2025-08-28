# Enhanced DSL Generator with Validation

## Overview

The enhanced DSL generator now includes comprehensive validation and regeneration capabilities to ensure that generated workflows only use tools and slugs that are actually available in the catalog.

## Key Features

### 1. Catalog Compliance Validation
- **Pre-validation Check**: Before running full validation, the generator performs a quick catalog compliance check
- **Real-time Verification**: Ensures every `toolkit_slug`, `trigger_id`, and `action_name` exists in the available catalog
- **Immediate Feedback**: Catches catalog violations early to avoid unnecessary validation cycles

### 2. Multi-Stage Validation
- **Schema Validation**: Ensures the generated workflow follows the DSL schema
- **Catalog Validation**: Verifies all toolkit and action references exist
- **Business Rule Validation**: Applies domain-specific validation rules
- **Linting**: Provides warnings and hints for best practices

### 3. Intelligent Regeneration
- **Automatic Retry**: If validation fails, the generator automatically regenerates the workflow
- **Configurable Attempts**: Default maximum of 3 regeneration attempts (configurable)
- **Smart Prompting**: Enhanced prompts with explicit instructions to use only available tools
- **Failure Handling**: Returns detailed error information if all attempts fail

### 4. Enhanced Prompt Engineering
- **Critical Instructions**: Prompts now include explicit warnings against inventing tools
- **Catalog Validation Rules**: Clear instructions about using only available tools
- **Fallback Guidance**: Instructions for creating minimal valid workflows when full workflows aren't possible

## How It Works

### 1. Generation Loop
```
Start Generation
    ↓
Generate Claude Prompt (with catalog data)
    ↓
Call Claude API
    ↓
Parse Response
    ↓
Check Catalog Compliance ← NEW
    ↓
Run Full Validation
    ↓
If Valid → Return Success
    ↓
If Invalid → Regenerate (up to max attempts)
```

### 2. Catalog Compliance Check
The generator performs a quick check to verify:
- All `toolkit_slug` references exist in available providers
- All `trigger_id` references exist in available triggers  
- All `action_name` references exist in available actions
- All connection toolkit references are valid

### 3. Validation Pipeline
1. **Schema Validation**: JSON schema conformance
2. **Catalog Validation**: Toolkit/action existence verification
3. **Business Rules**: Domain-specific validation
4. **Linting**: Best practice checks and warnings

## Usage

### Basic Usage
```python
from services.dsl_generator.generator import DSLGeneratorService
from services.dsl_generator.models import GenerationRequest

# Initialize service
generator = DSLGeneratorService()
await generator.initialize()

# Generate workflow
request = GenerationRequest(
    user_prompt="Send Slack message on email arrival",
    workflow_type="template",
    complexity="simple",
    selected_apps=["slack", "gmail"]
)

response = await generator.generate_workflow(request)
```

### Configuration
```python
# Set maximum regeneration attempts
generator.max_regeneration_attempts = 5

# Check catalog status
cache_status = generator.get_cache_status()
catalog_summary = generator.get_catalog_summary()
```

## Error Handling

### Validation Failures
- **Catalog Compliance**: Workflow uses unavailable tools
- **Schema Validation**: Workflow doesn't match DSL schema
- **Business Rules**: Workflow violates domain constraints

### Regeneration Logic
- **Attempt 1**: Initial generation with enhanced prompts
- **Attempt 2**: Regeneration with additional context
- **Attempt 3**: Final attempt with fallback instructions
- **Failure**: Returns detailed error information

## Monitoring and Debugging

### Logging
The generator provides detailed logging at each stage:
- Generation attempts and progress
- Catalog compliance check results
- Validation results and errors
- Regeneration decisions

### Status Information
```python
# Get cache status
cache_status = generator.get_cache_status()

# Get catalog summary
catalog_summary = generator.get_catalog_summary()

# Check if service is ready
if generator.catalog_service:
    print("Catalog service available")
```

## Best Practices

### 1. Catalog Management
- Ensure catalog data is up-to-date
- Monitor cache TTL and refresh when needed
- Validate catalog data integrity

### 2. Prompt Engineering
- Use specific app selections when possible
- Provide clear, detailed user prompts
- Consider workflow complexity requirements

### 3. Error Handling
- Check response success before processing
- Handle validation failures gracefully
- Provide user feedback on generation issues

## Testing

### Test Script
Use the provided test script to verify functionality:
```bash
python test_enhanced_generator.py
```

### Manual Testing
1. Test with various workflow types (template, executable, DAG)
2. Test with different complexity levels
3. Test with and without app selections
4. Verify catalog compliance enforcement

## Troubleshooting

### Common Issues

#### 1. Catalog Not Available
- Check database connection
- Verify Redis cache status
- Check catalog service initialization

#### 2. Validation Failures
- Review generated workflow structure
- Check catalog data completeness
- Verify schema definition

#### 3. Regeneration Loops
- Check prompt clarity and specificity
- Verify catalog data availability
- Review validation error details

### Debug Commands
```python
# Force catalog refresh
await generator.refresh_catalog_cache(force=True)

# Clear cache
generator.clear_catalog_cache()

# Get detailed status
status = generator.get_cache_status()
summary = generator.get_catalog_summary()
```

## Performance Considerations

- **Cache TTL**: Default 1 hour, adjust based on catalog update frequency
- **Regeneration Limits**: Default 3 attempts, balance between success rate and performance
- **Validation Pipeline**: Sequential validation to fail fast on critical errors

## Future Enhancements

- **Parallel Validation**: Run validation stages concurrently
- **Smart Regeneration**: Use validation feedback to improve prompts
- **Catalog Analytics**: Track tool usage patterns for optimization
- **A/B Testing**: Compare different prompt strategies
