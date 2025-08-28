# Workflow Validation and Linting Tools

This document explains how to use the validation and linting tools for workflow JSON files.

## Quick Start

### Simple Validation Script
Use the convenience script in the project root:

```bash
# Validate and lint a single file
python validate_workflow.py core/dsl/template_example.json

# Examples
python validate_workflow.py core/dsl/executable_example.json
python validate_workflow.py core/dsl/dag_example.json
```

### Advanced CLI Tool
For more control, use the full CLI tool in the validator directory:

```bash
# Navigate to validator directory
cd core/validator

# Validate only
python cli.py validate ../../core/dsl/template_example.json

# Lint only
python cli.py lint ../../core/dsl/executable_example.json

# Both validation and linting
python cli.py validate-and-lint ../../core/dsl/dag_example.json

# Save results to file
python cli.py validate-and-lint ../../core/dsl/template_example.json --output results.json

# Fast validation mode
python cli.py validate ../../core/dsl/executable_example.json --fast

# Strict linting mode
python cli.py lint ../../core/dsl/executable_example.json --strict
```

## What Each Tool Does

### 1. **Validator** (`validate`)
- Ensures workflow documents are structurally correct
- Checks against JSON schema
- Validates required fields and data types
- Output: Binary result (valid/invalid) with validation errors

### 2. **Linter** (`lint`)
- Provides guidance and best practices
- Checks business rules and catalog references
- Identifies potential issues and improvements
- Output: Detailed report with errors, warnings, and hints

### 3. **Comprehensive Analysis** (`validate-and-lint`)
- Runs both validation and linting
- Provides complete workflow analysis
- Shows overall readiness for execution

## Output Format

All tools output results in JSON format for easy parsing:

```json
{
  "timestamp": "2025-08-27T21:38:21.461926",
  "workflow_analysis": {
    "validation": { ... },
    "linting": { ... }
  },
  "overall_summary": {
    "workflow_valid": true,
    "has_lint_errors": false,
    "ready_for_execution": true
  }
}
```

## Error Codes

The validator and linter use standardized error codes:

- **E001**: Unknown toolkit/action references
- **E002**: Parameter specification mismatches  
- **E003**: Unknown triggers
- **E004**: Missing required scopes/connections
- **E006**: Graph integrity violations
- **E008**: Unresolved references
- **E010**: Missing trigger IDs

## Workflow Stages

The tools automatically detect and validate against the appropriate stage:

- **Template**: Initial workflow specification with placeholders
- **Executable**: Concrete workflow ready for execution
- **DAG**: Compiled execution graph

## Examples

### Template Workflow
```bash
python validate_workflow.py core/dsl/template_example.json
```
- Validates basic structure
- Checks required fields
- Identifies missing information

### Executable Workflow
```bash
python validate_workflow.py core/dsl/executable_example.json
```
- Validates complete structure
- Checks catalog references
- Validates connections and scopes

### DAG Workflow
```bash
python validate_workflow.py core/dsl/dag_example.json
```
- Validates graph structure
- Checks node and edge integrity
- Ensures execution readiness

## Integration

These tools can be integrated into:

- **CI/CD pipelines** for automated validation
- **Development workflows** for real-time feedback
- **API endpoints** for web-based validation
- **CLI tools** for command-line usage

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you're running from the project root
2. **Schema Errors**: Check that your JSON follows the expected structure
3. **Catalog Errors**: Verify toolkit and action references exist
4. **Connection Errors**: Ensure required connections are specified

### Getting Help

- Check the schema definition in `core/dsl/schema.json`
- Review example files in `core/dsl/`
- Use `--help` flag with CLI tools
- Check validation output for specific error details
