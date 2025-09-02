# Tool Hallucination Detection

## Overview

The DSL Generator now includes an **Aggressive Pre-Validation Check** that immediately detects when the LLM generates workflows using tools that weren't in its context. This prevents the common issue of "tool hallucination" where the LLM invents tools that don't exist.

## How It Works

### 1. Immediate Detection
After the LLM response is parsed but before the full validation runs, the system performs a fast, targeted check:

```python
# --- NEW: AGGRESSIVE PRE-VALIDATION CHECK ---
if parsed_response.success and parsed_response.dsl_template:
    dsl_dict = parsed_response.dsl_template
    if hasattr(dsl_dict, 'dict'):
        dsl_dict = dsl_dict.dict()
    
    tool_errors = self._check_tool_hallucinations(dsl_dict, catalog_context)
    if tool_errors:
        logger.warning(f"Tool Hallucination Detected: {tool_errors}")
        previous_errors.extend(tool_errors)
        continue  # Force a retry with this specific feedback
# ---------------------------------------------
```

### 2. Fast Tool Validation
The `_check_tool_hallucinations` method quickly validates:
- **Triggers**: Checks if `toolkit_slug.composio_trigger_slug` exists in available tools
- **Actions**: Checks if `toolkit_slug.action_name` exists in available tools

### 3. Immediate Feedback Loop
When hallucinations are detected:
- Errors are logged with specific details
- The generation loop immediately retries
- Previous errors are extended with the new tool validation errors
- The LLM gets precise feedback about what tools are invalid

## Benefits

### 🚀 **Immediate Feedback**
- No waiting for full validation pipeline
- Instant detection of tool misuse
- Faster retry cycles

### 🎯 **Precise Error Messages**
Instead of generic "Validation Failed", the LLM gets:
```
"Invalid action: 'slack.POST_MESSAGE'. It is not in the <available_tools> list."
"Invalid trigger: 'gmail.NON_EXISTENT'. It is not in the <available_tools> list."
```

### 🔄 **Efficient Retry Loop**
- Prevents wasted time on invalid workflows
- Forces immediate correction of tool usage
- Maintains context of previous errors

## Implementation Details

### Method Signature
```python
def _check_tool_hallucinations(self, dsl: Dict[str, Any], catalog_context: Dict[str, Any]) -> List[str]:
    """
    A simple, fast check to see if the LLM used tools that weren't in its context.
    Returns a list of error strings for feedback.
    """
```

### Error Format
Errors follow this pattern:
- `"Invalid trigger: '{toolkit}.{trigger}'. It is not in the <available_tools> list."`
- `"Invalid action: '{toolkit}.{action}'. It is not in the <available_tools> list."`

### Integration Point
The check is integrated into `_generate_with_validation_loop` right after:
1. Response parsing
2. Before existing validation logic
3. Before the full validator call

## Example Workflow

### Before (Generic Error)
```
LLM generates workflow → Full validation runs → Generic "Validation Failed" → Retry with vague feedback
```

### After (Immediate Detection)
```
LLM generates workflow → Immediate tool check → Specific "Invalid action: 'slack.POST_MESSAGE'" → Retry with precise feedback
```

## Testing

Run the test suite to verify functionality:

```bash
cd services/dsl_generator
python test_tool_hallucination.py
```

The tests verify:
- ✅ Valid workflows pass
- ❌ Invalid triggers are detected
- ❌ Invalid actions are detected  
- ❌ Invalid toolkits are detected
- ❌ Multiple errors are reported

## Performance Impact

- **Minimal overhead**: Simple set lookups
- **Fast execution**: O(n) where n = number of tools in workflow
- **Early termination**: Prevents expensive validation on invalid workflows

## Future Enhancements

Potential improvements could include:
- Tool parameter validation
- Schema compliance checking
- Dependency validation between tools
- Custom error message templates

## Troubleshooting

### Common Issues

1. **False Positives**: Ensure catalog context is properly populated
2. **Missing Tools**: Check if toolkit slugs match exactly
3. **Case Sensitivity**: Verify tool names match the catalog exactly

### Debug Logging

Enable debug logging to see detailed validation steps:
```python
logging.getLogger(__name__).setLevel(logging.DEBUG)
```

## Conclusion

The Aggressive Pre-Validation Check significantly improves the reliability of workflow generation by:
- Catching tool hallucinations immediately
- Providing precise feedback to the LLM
- Reducing validation cycles
- Improving overall generation success rate

This feature addresses the core issue of LLM tool misuse while maintaining performance and providing clear, actionable feedback for the retry loop.
