# Weave Linter & Validator Service

A comprehensive validation and linting service for Template, Executable, and DAG workflow specifications.

## Overview

The Weave Linter & Validator Service provides:

- **JSON Schema Validation**: Ensures documents conform to the workflow DSL schema
- **Catalog Validation**: Verifies toolkit and action references against the actual catalog
- **Business Rule Validation**: Applies domain-specific validation rules
- **Linting**: Provides warnings and hints for best practices
- **Auto-repair**: Automatically fixes common issues when possible
- **Compilation**: Converts executable workflows to DAG format

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Validator                          │
├─────────────────────────────────────────────────────────────┤
│  validate()  │  lint()  │  attempt_repair()  │  compile() │
└─────────────────────────────────────────────────────────────┘
           │           │              │           │
           ▼           ▼              ▼           ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Schema    │ │    Rules    │ │   Catalog   │ │  Compiler   │
│ Validator   │ │  Engine     │ │ Validator   │ │   Engine    │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

## Quick Start

### Basic Validation

```python
from core.validator import validate, Stage
from core.validator.types import ValidateOptions

# Validate a template workflow
result = await validate(Stage.TEMPLATE, template_doc)

if result.ok:
    print("Template is valid!")
else:
    for error in result.errors:
        print(f"Error: {error.message} at {error.path}")
```

### Linting with Context

```python
from core.validator import lint, Stage
from core.validator.types import LintContext, LintOptions

# Create linting context with catalog and connections
context = LintContext(
    catalog=catalog_data,
    connections=connection_data
)

# Lint an executable workflow
lint_report = await lint(Stage.EXECUTABLE, executable_doc, context)

print(f"Found {len(lint_report.errors)} errors")
print(f"Found {len(lint_report.warnings)} warnings")
print(f"Found {len(lint_report.hints)} hints")
```

### Validate and Compile

```python
from core.validator import validate_and_compile
from core.validator.types import CompileContext

# Create compilation context
context = CompileContext(
    catalog=catalog_data,
    connections=connection_data
)

# Validate and compile to DAG
result = await validate_and_compile(executable_doc, context)

if result.ok:
    dag = result.compiled
    print(f"Compiled DAG with {len(dag['nodes'])} nodes")
else:
    print("Compilation failed")
```

## JSON Output

The validator service provides structured JSON output for easy integration with other systems:

```python
from core.validator import (
    validation_to_json, lint_to_json, compile_to_json, 
    comprehensive_to_json, comprehensive_to_dict
)

# Convert results to JSON strings
validation_json = validation_to_json(result, pretty=True)
lint_json = lint_to_json(lint_result, pretty=True)
compile_json = compile_to_json(compile_result, pretty=True)

# Get comprehensive results as JSON
comprehensive_json = comprehensive_to_json(validation_result, lint_result, compile_result, pretty=True)

# Get comprehensive results as Python dict
comprehensive_dict = comprehensive_to_dict(validation_result, lint_result, compile_result)
```

### JSON Output Structure

**Validation Response:**
```json
{
  "success": true,
  "timestamp": "2025-08-26T18:53:04.219760",
  "stage": "validation",
  "errors": [],
  "summary": {
    "total_errors": 0,
    "validation_passed": true
  }
}
```

**Linting Report:**
```json
{
  "timestamp": "2025-08-26T18:53:04.219760",
  "stage": "linting",
  "findings": {
    "errors": [
      {
        "code": "E001",
        "path": "workflow.actions[].toolkit_slug",
        "message": "Unknown toolkit: slack",
        "severity": "ERROR",
        "hint": "Ensure the toolkit exists in the catalog",
        "docs": null,
        "meta": {}
      }
    ],
    "warnings": [],
    "hints": []
  },
  "summary": {
    "total_errors": 1,
    "total_warnings": 0,
    "total_hints": 0,
    "has_errors": true,
    "has_warnings": false,
    "has_hints": false
  }
}
```

**Comprehensive Report:**
```json
{
  "timestamp": "2025-08-26T18:53:04.219760",
  "workflow_analysis": {
    "validation": { ... },
    "linting": { ... }
  },
  "compilation": { ... },
  "overall_summary": {
    "workflow_valid": true,
    "has_lint_errors": true,
    "has_lint_warnings": false,
    "compilation_successful": true,
    "ready_for_execution": false
  }
}
```

## Workflow Stages

### 1. Template Stage
- High-level workflow intent
- Placeholders allowed for missing information
- Basic structure validation
- Catalog reference validation

### 2. Executable Stage
- Fully resolved workflow with concrete values
- All toolkit/action references must exist in catalog
- Connection IDs must be provided for authenticated actions
- Trigger slugs must be concrete
- Parameter validation against catalog specs

### 3. DAG Stage
- Runtime execution graph
- Node and edge integrity validation
- Cycle detection
- Reachability analysis

## Validation Rules

The validator uses a rule-based system for validation and linting. Each finding includes a structured error code for easy programmatic handling.

### Error Code Format

Error codes follow the pattern `E###` where:
- **E001**: Unknown toolkit or action
- **E002**: Parameter specification mismatch  
- **E003**: Unknown trigger
- **E004**: Missing required scopes
- **E005**: Authentication requirement mismatch
- **E006**: Graph integrity violation

### Finding Structure

Each linting finding includes:
- **`code`**: The error code (e.g., "E001")
- **`path`**: JSON path to the problematic field
- **`message`**: Human-readable error description
- **`severity`**: ERROR, WARNING, or HINT
- **`hint`**: Suggested fix or guidance
- **`docs`**: Link to documentation (if available)
- **`meta`**: Additional metadata about the finding

### Example Finding

```json
{
  "code": "E001",
  "path": "workflow.actions[].toolkit_slug",
  "message": "Unknown toolkit: slack",
  "severity": "ERROR",
  "hint": "Ensure the toolkit exists in the catalog",
  "docs": null,
  "meta": {}
}
```

### Error Rules (Blocking)
- `E001`: Unknown toolkit/action/trigger
- `E002`: Parameter specification mismatch
- `E004`: Missing required scopes/connections
- `E006`: Graph integrity violation
- `E008`: Unresolved reference
- `E010`: Missing trigger ID

### Warning Rules (Non-blocking)
- `W101`: Deprecated action
- `W102`: Version drift
- `W201`: Aggressive fanout
- `W203`: Weak trigger filter

### Hint Rules (Guidance)
- `H001`: Missing recommended parameter
- `H002`: Performance optimization opportunity

## Configuration

### Validation Options

```python
from core.validator.types import ValidateOptions

opts = ValidateOptions(
    fast=False,        # Enable fast mode for executor preflight
    fail_fast=True     # Stop on first error
)
```

### Linting Options

```python
from core.validator.types import LintOptions

opts = LintOptions(
    level="strict",     # "standard" or "strict"
    max_findings=100    # Limit total findings
)
```

## Integration with Catalog

The validator integrates with the catalog service to:

1. **Verify Toolkit Existence**: Check that referenced toolkits exist
2. **Validate Actions**: Ensure actions exist within toolkits
3. **Check Triggers**: Verify trigger slugs are valid
4. **Validate Parameters**: Match input parameters against catalog specs
5. **Scope Validation**: Ensure connections have required scopes

## Performance

### SLOs
- **Schema validation**: < 50ms simple, < 120ms complex
- **Catalog validation**: < 120ms cached, < 400ms if refresh needed
- **Linting**: < 200ms simple, < 500ms complex
- **Fast mode**: < 30ms for executor preflight

### Caching
- Redis-based caching for catalog data
- Configurable TTL and stale thresholds
- Performance optimization for repeated validations

## Error Handling

### Validation Errors
- Structured error objects with codes, paths, and messages
- Stage-specific error context
- Detailed metadata for debugging

### Linting Findings
- Categorized by severity (ERROR, WARNING, HINT)
- Actionable hints and documentation links
- Configurable finding limits

## Auto-Repair

The service can automatically fix common issues:

- **Type Bridge Insertion**: Add transform nodes for type mismatches
- **Default Values**: Insert missing required parameters
- **Connection Setup**: Add default connection configurations
- **Webhook Security**: Enable signature verification

## Testing

### Running Examples

```bash
cd core/validator
python example.py
```

### Test Coverage
- Golden test cases for common workflows
- Edge case validation
- Performance benchmarking
- Rule coverage verification

## Extending the Service

### Adding New Rules

```python
from core.validator.types import Rule, Stage

new_rule = Rule(
    id="W999",
    stage=[Stage.EXECUTABLE],
    severity="WARNING",
    message="Custom warning message",
    docs="/rules/W999",
    auto_repairable=False,
    applies=lambda doc, ctx: True,
    check=lambda doc, ctx: []
)

# Register the rule
from core.validator.rules import rule_registry
rule_registry.register_rule(new_rule)
```

### Custom Validators

```python
from core.validator.types import ValidationError, Stage

async def custom_validator(doc: dict, stage: Stage) -> List[ValidationError]:
    errors = []
    # Custom validation logic
    return errors
```

## Dependencies

- `jsonschema`: JSON Schema validation
- `redis`: Caching and performance optimization
- `asyncio`: Asynchronous operation support

## Future Enhancements

- **Expression Engine**: Safe expression parsing and validation
- **Dataflow Analysis**: Advanced graph analysis and optimization
- **Provider-Specific Rules**: Custom validation for specific toolkits
- **Machine Learning**: Intelligent suggestion and auto-repair
- **Real-time Validation**: Live validation in UI builders
