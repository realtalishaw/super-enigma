# Workflow Execution Engine

A microservice for executing DAG workflows using Composio for tool execution. This executor supports idempotency, retries, conditional logic, parallel execution, joins, and loops.

## Features

- **Language-agnostic**: Works with any DAG JSON conforming to the schema
- **Single-process orchestrator**: Lightweight and efficient
- **Composio integration**: Executes actions through Composio's API
- **Advanced flow control**: IF/ELSE, SWITCH, parallel execution, joins, loops
- **Idempotency**: Prevents duplicate side-effects from retries
- **Retry policies**: Configurable retry logic with backoff strategies
- **Template rendering**: Jinja2 templates for dynamic input generation
- **Multiple execution modes**: Can be called from APIs, scripts, or CLI

## Architecture

The executor follows the architecture defined in `docs/tech_specs/executor.md`:

1. **Boot**: Initialize state store, cache, and metrics
2. **Preflight**: Validate DAG structure and runtime safety
3. **Trigger Registration**: Register event-based and schedule-based triggers
4. **Activation**: Convert external events into workflow runs
5. **Orchestration**: Execute nodes in topological order
6. **Action Execution**: Call Composio with retries and idempotency
7. **Routing**: Navigate to successor nodes based on conditions
8. **Finalization**: Update run status and emit summaries

## Installation

The executor is part of the workflow-automation-engine project. Install dependencies:

```bash
# From the project root
pip install -r services/executor/requirements.txt

# Or install the main project requirements
pip install -r requirements.txt
```

## Configuration

Set environment variables for Composio integration:

```bash
export COMPOSIO_BASE_URL="https://api.composio.dev"
export COMPOSIO_API_KEY="your_api_key_here"
```

## Usage

### 1. As a Python Module

```python
from services.executor import run_workflow, execute_workflow_async

# Synchronous execution
run_id = run_workflow(
    dag=workflow_dag,
    event_payload=event_data,
    user_id="user123",
    workflow_id="wf001"
)

# Asynchronous execution
run_id = await execute_workflow_async(
    dag=workflow_dag,
    event_payload=event_data,
    user_id="user123",
    workflow_id="wf001"
)
```

### 2. From API Endpoints

```python
from fastapi import FastAPI
from services.executor import execute_workflow_async

app = FastAPI()

@app.post("/execute-workflow")
async def execute_workflow_endpoint(request: dict):
    run_id = await execute_workflow_async(
        dag=request["dag"],
        event_payload=request["event_payload"],
        user_id=request["user_id"],
        workflow_id=request.get("workflow_id")
    )
    return {"run_id": run_id, "status": "started"}
```

### 3. From CLI

```bash
# Execute a workflow
python services/executor/cli.py execute \
    --dag workflow.json \
    --event event.json \
    --user-id USER123

# Validate a DAG
python services/executor/cli.py validate --dag workflow.json

# Check run status
python services/executor/cli.py run-status --run-id abc123
```

### 4. From Scripts

```bash
# Simple script execution
python services/executor/run_workflow.py workflow.json event.json USER123
```

## DAG Schema

The executor expects DAG JSON conforming to the schema in `core/dsl/schema.json`. Key node types:

- **trigger**: Event-based or schedule-based triggers
- **action**: Composio tool actions
- **gateway_if**: Conditional branching
- **gateway_switch**: Switch-case branching
- **parallel**: Fan-out execution
- **join**: Synchronization points
- **loop_while**: Conditional loops
- **loop_foreach**: Iterative loops

## Example DAG

```json
{
  "schema_type": "dag",
  "nodes": [
    {
      "id": "trigger_1",
      "type": "trigger",
      "data": {
        "trigger": {
          "kind": "event_based",
          "toolkit_slug": "email",
          "composio_trigger_slug": "new_email"
        }
      }
    },
    {
      "id": "action_1",
      "type": "action",
      "data": {
        "tool": "slack",
        "action": "send_message",
        "connection_id": "slack_conn_1",
        "input_template": {
          "channel": "#general",
          "message": "New email received: {{ inputs.subject }}"
        }
      }
    }
  ],
  "edges": [
    {
      "source": "trigger_1",
      "target": "action_1"
    }
  ]
}
```

## State Management

The executor uses in-memory storage by default:

- **StateStore**: Tracks runs and node executions
- **IdempotencyCache**: Prevents duplicate action execution
- **ExecutionContext**: Manages variables and artifacts during execution

For production use, replace with:
- **Database**: PostgreSQL/MySQL for persistent state
- **Redis**: For distributed idempotency cache
- **Message Queue**: For async execution and retries

## Error Handling

- **Retriable errors**: Automatically retried based on policy
- **Fatal errors**: Stop execution and mark run as failed
- **Node failures**: Individual nodes can fail without stopping the workflow
- **Conditional routing**: Edges can specify success/error conditions

## Monitoring

The executor provides:
- **Run status**: Track workflow execution progress
- **Node execution history**: Detailed logs of each node
- **Error tracking**: Capture and store error details
- **Metrics**: Success/failure counts by tool and reason

## Development

### Running Tests

```bash
# From the project root
python -m pytest services/executor/tests/
```

### Adding New Node Types

1. Add node type to `NodeType` enum
2. Implement execution logic in `_execute_node`
3. Add validation in `_validate_dag`
4. Update documentation

### Extending Composio Integration

The `ComposioClient` class handles all Composio API calls. Extend it to support:
- Additional authentication methods
- Rate limiting
- Webhook handling
- Connection management

## Production Considerations

- **Persistence**: Replace in-memory storage with database
- **Scaling**: Use message queues for distributed execution
- **Monitoring**: Add metrics collection and alerting
- **Security**: Validate DAGs and sanitize inputs
- **Caching**: Use Redis for idempotency and performance
- **Logging**: Structured logging for debugging and audit

## Troubleshooting

### Common Issues

1. **Missing Composio credentials**: Set environment variables
2. **Invalid DAG**: Use validation command to check structure
3. **Template errors**: Check Jinja2 syntax in input templates
4. **Connection failures**: Verify Composio API connectivity

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger("services.executor").setLevel(logging.DEBUG)
```

## Contributing

1. Follow the existing code structure
2. Add tests for new functionality
3. Update documentation
4. Ensure compatibility with the schema

## License

Part of the workflow-automation-engine project.
