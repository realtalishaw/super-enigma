# Multiple Suggestions Generation

This document explains how to use the new multiple suggestions generation functionality in the workflow automation engine.

## Overview

The API now supports generating multiple workflow suggestions in parallel, allowing users to get 1-5 different workflow options for their automation needs. This feature provides variety and choice while maintaining performance through parallel execution.

## API Changes

### Request Model

The `PlanRequest` model now includes an optional `num_suggestions` parameter:

```python
class PlanRequest(BaseModel):
    user_id: str
    user_request: Optional[str] = None
    selected_apps: Optional[List[str]] = []
    num_suggestions: Optional[int] = Field(default=1, ge=1, le=5, description="Number of suggestions to generate (1-5)")
```

### Usage Examples

#### Generate Single Suggestion (Default)
```python
request = {
    "user_id": "user123",
    "user_request": "Send a notification when a new email arrives",
    "selected_apps": ["gmail"]
    # num_suggestions defaults to 1
}
```

#### Generate Multiple Suggestions
```python
request = {
    "user_id": "user123",
    "user_request": "Send a notification when a new email arrives",
    "selected_apps": ["gmail"],
    "num_suggestions": 3  # Will generate 3 different workflow options
}
```

## Backend Implementation

### New Method: `generate_multiple_workflows`

The DSL generator service now includes a new method for parallel generation:

```python
async def generate_multiple_workflows(
    self, 
    request: GenerationRequest, 
    num_workflows: int = 1
) -> List[GenerationResponse]:
    """
    Generate multiple workflow DSL templates in parallel.
    
    Args:
        request: Generation request with user prompt and context
        num_workflows: Number of workflows to generate (1-5)
        
    Returns:
        List of GenerationResponse objects
    """
```

### Parallel Execution

- Uses `asyncio.gather()` for concurrent execution
- Each generation runs independently in parallel
- Adds small variations to prompts to encourage diversity
- Handles failures gracefully with fallback responses
- Maintains backward compatibility (single generation still works)

### Performance Benefits

- **Parallel Execution**: Multiple workflows generate simultaneously
- **Faster Total Time**: Significantly faster than sequential generation
- **Resource Efficiency**: Better utilization of API rate limits
- **User Experience**: Users get multiple options without waiting

## Response Format

The API now returns multiple suggestions in the `PlanResponse`:

```python
class PlanResponse(BaseModel):
    suggestions: List[Suggestion]  # Now contains 1-5 suggestions
```

Each suggestion includes:
- Unique `suggestion_id`
- Workflow title and description
- DSL parametric structure
- Confidence score
- Missing fields (if any)
- Full workflow JSON for preview

## Error Handling

### Individual Generation Failures
- If one generation fails, others continue
- Failed generations return fallback suggestions
- Error messages are preserved for debugging

### Validation and Fallbacks
- Each suggestion is processed independently
- Database saving failures don't affect other suggestions
- Graceful degradation maintains user experience

## Testing

### Test Script
Run the test script to verify functionality:

```bash
python test_multiple_suggestions.py
```

### Evaluation Script
The evaluation script now includes multiple generation testing:

```bash
python evals/run_evals.py
```

## Configuration

### Limits
- **Minimum**: 1 suggestion (default)
- **Maximum**: 5 suggestions
- **Validation**: Input validation prevents invalid values

### Rate Limiting
- Respects existing API rate limits
- Parallel execution may hit rate limits faster
- Consider adjusting rate limit delays if needed

## Migration Guide

### Existing Code
Existing code continues to work unchanged:
- `num_suggestions` defaults to 1
- Single suggestion behavior preserved
- No breaking changes to existing endpoints

### New Features
To use multiple suggestions:
1. Add `num_suggestions` parameter to requests
2. Handle multiple suggestions in responses
3. Consider UI updates to display multiple options

## Best Practices

### When to Use Multiple Suggestions
- **User Choice**: When users want workflow options
- **A/B Testing**: Compare different automation approaches
- **Complex Workflows**: Multiple valid solutions exist
- **User Education**: Show different automation patterns

### Performance Considerations
- **API Costs**: Multiple generations increase API usage
- **Rate Limits**: Monitor rate limit impacts
- **User Experience**: Balance speed vs. choice
- **Resource Usage**: Consider server resource implications

## Troubleshooting

### Common Issues

#### Rate Limit Errors
- Reduce `num_suggestions` value
- Increase rate limit delays
- Implement exponential backoff

#### Generation Failures
- Check individual error messages
- Verify API key configuration
- Review catalog availability

#### Performance Issues
- Monitor generation times
- Check parallel execution logs
- Verify asyncio configuration

### Debug Information
The API provides detailed logging:
- Generation timing for each suggestion
- Success/failure status per workflow
- Error details for failed generations
- Performance metrics and comparisons

## Future Enhancements

### Planned Features
- **Smart Variation**: AI-driven prompt variations
- **Quality Filtering**: Rank suggestions by quality
- **User Preferences**: Learn from user choices
- **Template Libraries**: Reuse successful patterns

### Performance Optimizations
- **Caching**: Cache common generation patterns
- **Batch Processing**: Optimize parallel execution
- **Resource Management**: Better rate limit handling
- **Async Optimization**: Improve concurrent performance
