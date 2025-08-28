# Workflow DSL Compilers

This package contains the two main compilers for the workflow automation engine:

1. **Template Materializer (T→E)**: Converts high-level Template JSON with placeholders into fully-resolved Executable JSON
2. **Graph Lowerer (E→D)**: Lowers concrete Executable JSON into executor/UI-ready DAG JSON (nodes + edges + routing)

## Architecture

```
Template JSON → Template Materializer → Executable JSON → Graph Lowerer → DAG JSON
     (T)              (T→E)                (E)              (E→D)         (D)
```

### Template Materializer (T→E)

The Template Materializer hydrates intent into something runnable by:

- **Filling placeholders**: Substitute `{{...}}` using user answers
- **Resolving providers/actions/triggers**: Lookup in catalog and resolve connections
- **Parameter normalization**: Coerce types and fill required parameters
- **Policy injection**: Attach retry, timeout, and rate limit policies
- **Security validation**: Reject plaintext secrets and validate connections

**Input**: Template JSON + Context (catalog, user, connections, answers, defaults)
**Output**: Executable JSON + Report (errors, warnings, repairs)

### Graph Lowerer (E→D)

The Graph Lowerer turns concrete steps and flow-control intent into an executable graph with:

- **Explicit node types**: trigger, action, gateway_if, parallel, join, loop
- **Edges with routing**: Success/error conditions and expressions
- **Flow control**: IF/ELSE, parallel execution, loops
- **UI metadata**: Labels, icons, positions for React Flow

**Input**: Executable JSON + Context (catalog, layout options, uiDefaults)
**Output**: DAG JSON + Report (warnings, hints)

## Installation

The compilers are part of the `services/dsl_generator` package. No additional dependencies are required beyond the standard Python environment.

## Usage

### Python API

```python
from compilers import TemplateMaterializer, GraphLowerer

# 1. Template Materializer
materializer = TemplateMaterializer()
result = materializer.compile(template_doc, ctx)

if result["executable_doc"]:
    executable = result["executable_doc"]
    print("Compilation successful!")
else:
    print("Compilation failed:", result["report"].errors)

# 2. Graph Lowerer
lowerer = GraphLowerer()
result = lowerer.compile(executable, ctx)

if result["dag_doc"]:
    dag = result["dag_doc"]
    print("DAG generation successful!")
else:
    print("DAG generation failed:", result["report"].errors)
```

### CLI Interface

The compilers include a command-line interface for development and testing:

```bash
# Compile template to executable
python -m compilers.cli template \
  --in template.json \
  --out executable.json \
  --catalog catalog.json \
  --connections connections.json \
  --answers answers.json \
  --defaults defaults.json

# Compile executable to DAG
python -m compilers.cli dag \
  --in executable.json \
  --out dag.json \
  --layout dagre
```

## Context Objects

### Template Materializer Context

```python
ctx = {
    "catalog": {
        "providers": [
            {
                "slug": "salesforce",
                "toolkits": [
                    {
                        "slug": "salesforce",
                        "triggers": [...],
                        "actions": [...]
                    }
                ]
            }
        ]
    },
    "user": {
        "id": "user123",
        "tenant_id": "tenant456"
    },
    "connections": {
        "salesforce_conn": {
            "provider": "salesforce",
            "scopes": ["read_leads"]
        }
    },
    "answers": {
        "lead_email": "$.email",
        "lead_name": "$.first_name"
    },
    "defaults": {
        "retry": {"max_attempts": 3},
        "timeout_ms": 30000
    }
}
```

### Graph Lowerer Context

```python
ctx = {
    "catalog": {},  # Optional, for type hints
    "layout": "dagre",  # dagre, elk, or manual
    "uiDefaults": {
        "icons": {...},
        "labels": {...}
    }
}
```

## Example Workflow

### 1. Template JSON

```json
{
  "workflow_id": "email_workflow",
  "version": "1.0.0",
  "triggers": [
    {
      "local_id": "new_lead",
      "toolkit_slug": "salesforce",
      "trigger_id": "new_lead",
      "connection_hint": "salesforce_conn"
    }
  ],
  "actions": [
    {
      "local_id": "send_email",
      "toolkit_slug": "sendgrid",
      "action_id": "send_email",
      "required_inputs": {
        "to": "{{lead_email}}",
        "subject": "Welcome {{lead_name}}!"
      }
    }
  ],
  "routes": [
    {
      "from_ref": "new_lead",
      "to_ref": "send_email"
    }
  ]
}
```

### 2. Executable JSON (after Template Materializer)

```json
{
  "workflow_id": "email_workflow",
  "version": "1.0.0",
  "triggers": [
    {
      "local_id": "new_lead",
      "exec": {
        "provider": "salesforce",
        "trigger_slug": "new_lead",
        "connection_id": "salesforce_conn",
        "configuration": {...}
      },
      "trigger_instance_id": "abc123..."
    }
  ],
  "actions": [
    {
      "local_id": "send_email",
      "exec": {
        "provider": "sendgrid",
        "action_slug": "send_email",
        "connection_id": "sendgrid_conn",
        "required_inputs": {
          "to": "$.email",
          "subject": "Welcome $.first_name!"
        },
        "retry": {"max_attempts": 3},
        "timeout_ms": 30000
      }
    }
  ]
}
```

### 3. DAG JSON (after Graph Lowerer)

```json
{
  "workflow_id": "email_workflow",
  "version": "1.0.0",
  "nodes": [
    {
      "id": "t1",
      "type": "trigger",
      "data": {
        "kind": "event_based",
        "tool": "salesforce",
        "slug": "new_lead"
      },
      "label": "New Lead Trigger"
    },
    {
      "id": "a1",
      "type": "action",
      "data": {
        "tool": "sendgrid",
        "action": "send_email"
      },
      "label": "Send Email"
    }
  ],
  "edges": [
    {
      "id": "e_t1_a1",
      "source": "t1",
      "target": "a1",
      "when": "success"
    }
  ]
}
```

## Testing

Run the test suite to see the compilers in action:

```bash
cd services/dsl_generator/compilers
python test_compilers.py
```

This will demonstrate the complete pipeline and save output files to the `output/` directory.

## Error Handling

Both compilers return detailed reports with:

- **Errors**: Critical issues that prevent compilation
- **Warnings**: Non-critical issues that should be addressed
- **Repairs**: Auto-fixes applied during compilation
- **Hints**: Suggestions for improvement

## Extending the Compilers

### Adding New Node Types

To add new node types in the Graph Lowerer:

1. Add the type to `_new_node_id()` counter
2. Add mapping to the index
3. Implement lowering logic in `_lower_flow_control()`

### Adding New Validation Rules

To add new validation rules:

1. Extend the validation methods in each compiler
2. Add appropriate error codes and messages
3. Update the test suite

## Dependencies

- **Core**: Standard Python libraries only
- **Optional**: dagre/ELK for advanced graph layout
- **Testing**: pytest for unit tests

## Contributing

When contributing to the compilers:

1. Follow the established patterns for error reporting
2. Add comprehensive tests for new features
3. Update documentation and examples
4. Ensure deterministic output (no random behavior)

## License

Part of the workflow automation engine project.
