# Cron Scheduler Service

A service that fires schedule-based triggers at the right times and starts workflow runs via the RunLauncher. It does not execute DAGs, does not talk to Composio, and does not manage actions. It only keeps time and initiates runs.

## Overview

The Cron Scheduler service consists of several key components:

- **SchedulerRegistrar**: Manages schedule registration and updates
- **SchedulerWorker**: Scans due schedules and starts workflow runs
- **RunLauncher**: Loads DAG JSON and calls the Executor
- **SchedulerDatabase**: Manages schedule and run data persistence

## Features

- **Schedule Management**: Register, modify, pause, and delete cron schedules
- **Timezone Support**: IANA timezone-aware scheduling with DST handling
- **Overlap Policies**: Configurable policies for handling overlapping runs (allow, skip, queue)
- **Catchup Policies**: Handle missed runs during downtime (none, fire_immediately, spread)
- **Jitter Support**: Random timing offsets to prevent thundering herd
- **Idempotency**: Ensures exactly one run per scheduled time
- **Leader Election**: Support for multi-instance deployment
- **Observability**: Metrics, logging, and status endpoints

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Compiler/     │    │   Scheduler     │    │   RunLauncher   │
│   Deployer      │───▶│   Registrar     │───▶│                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Scheduler     │    │    Executor     │
                       │   Worker        │    │                 │
                       └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Database      │
                       │   (SQLite)      │
                       └─────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
cd services/scheduler
pip install -r requirements.txt
```

### 2. Run the Service

```bash
python run.py
```

The service will start on `http://localhost:8001` by default.

### 3. Start the Worker

```bash
curl -X POST http://localhost:8001/worker/start
```

### 4. Create a Schedule

```bash
curl -X POST http://localhost:8001/schedules/upsert \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "example_workflow",
    "version": 1,
    "user_id": "user123",
    "cron_expr": "0 */5 * * * *",
    "timezone": "America/New_York"
  }'
```

## API Reference

### Schedule Management

#### Create/Update Schedule
```http
POST /schedules/upsert
```

**Request Body:**
```json
{
  "schedule_id": "optional_custom_id",
  "workflow_id": "workflow_123",
  "version": 1,
  "user_id": "user_456",
  "cron_expr": "0 */5 * * * *",
  "timezone": "America/New_York",
  "start_at": "2024-01-01T00:00:00Z",
  "end_at": "2024-12-31T23:59:59Z",
  "jitter_ms": 1000,
  "overlap_policy": "skip",
  "catchup_policy": "none"
}
```

#### Pause/Unpause Schedule
```http
POST /schedules/{schedule_id}/pause
```

**Request Body:**
```json
{
  "paused": true
}
```

#### Delete Schedule
```http
DELETE /schedules/{schedule_id}
```

#### Get Schedule
```http
GET /schedules/{schedule_id}
```

#### List Schedules
```http
GET /schedules?user_id=user123&workflow_id=workflow456&limit=100
```

### Worker Management

#### Start Worker
```http
POST /worker/start
```

#### Stop Worker
```http
POST /worker/stop
```

#### Get Worker Status
```http
GET /worker/status
```

### Run Launcher

#### Start Workflow
```http
POST /run-launcher/start?workflow_id=workflow123&version=1&user_id=user456&scheduled_for=2024-01-01T00:00:00Z&idempotency_key=abc123
```

### Observability

#### Health Check
```http
GET /health
```

#### Metrics
```http
GET /metrics
```

#### Schedule Runs
```http
GET /schedules/{schedule_id}/runs?limit=10
```

## Configuration

The service can be configured using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULER_HOST` | `0.0.0.0` | Host to bind to |
| `SCHEDULER_PORT` | `8001` | Port to bind to |
| `SCHEDULER_RELOAD` | `false` | Enable auto-reload for development |

## Cron Expression Format

The service supports standard cron expressions with 5 or 6 fields:

```
┌───────────── second (0-59) - optional
│ ┌───────────── minute (0-59)
│ │ ┌───────────── hour (0-23)
│ │ │ ┌───────────── day of month (1-31)
│ │ │ │ ┌───────────── month (1-12)
│ │ │ │ │ ┌───────────── day of week (0-7, Sunday is 0 or 7)
│ │ │ │ │ │
* * * * * *
```

**Examples:**
- `0 */5 * * * *` - Every 5 minutes
- `0 0 * * *` - Every hour at minute 0
- `0 0 0 * *` - Every day at midnight
- `0 0 12 * * 1` - Every Monday at noon

## Policies

### Overlap Policy

- **`allow`**: Multiple concurrent runs per schedule
- **`skip`**: Drop a tick if prior run hasn't finished
- **`queue`**: Defer until prior finishes (serial execution)

### Catchup Policy

- **`none`**: Ignore missed times during downtime
- **`fire_immediately`**: Emit all missed ticks next wake
- **`spread`**: Distribute missed ticks across the lookahead window

## Development

### Project Structure

```
services/scheduler/
├── __init__.py          # Package initialization
├── models.py            # Pydantic data models
├── database.py          # Database interface
├── cron_utils.py        # Cron expression utilities
├── registrar.py         # Schedule registration logic
├── run_launcher.py      # Workflow execution launcher
├── worker.py            # Scheduler worker process
├── api.py               # FastAPI endpoints
├── run.py               # Main entry point
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

### Adding New Features

1. **Models**: Add new Pydantic models in `models.py`
2. **Database**: Extend `SchedulerDatabase` class in `database.py`
3. **Business Logic**: Implement in appropriate service class
4. **API**: Add endpoints in `api.py`
5. **Tests**: Create test files in a `tests/` directory

### Testing

```bash
# Run tests (when implemented)
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=scheduler --cov-report=html
```

## Production Considerations

### Database

- Replace SQLite with PostgreSQL or similar production database
- Add connection pooling and connection management
- Implement proper database migrations

### Cron Parsing

- Replace simplified cron logic with `croniter` or similar library
- Add proper timezone and DST handling
- Implement cron expression validation

### Leader Election

- Replace file-based locking with Redis `SETNX` or Postgres advisory locks
- Add proper lock timeouts and cleanup
- Implement health checks for leader instances

### Monitoring

- Add Prometheus metrics
- Implement structured logging
- Add distributed tracing
- Set up alerting for failures

### Security

- Add authentication and authorization
- Implement rate limiting
- Add input validation and sanitization
- Use HTTPS in production

## Troubleshooting

### Common Issues

1. **Worker not starting**: Check if another instance is running (leader lock)
2. **Schedules not firing**: Verify worker is running and cron expressions are valid
3. **Database errors**: Check file permissions and disk space
4. **Workflow execution failures**: Verify executor service is accessible

### Logs

The service logs to stdout with structured logging. Key log levels:

- **INFO**: Normal operation, schedule changes, run starts
- **WARNING**: Non-critical issues, retries
- **ERROR**: Failures, exceptions, system errors
- **DEBUG**: Detailed execution flow (enable for troubleshooting)

### Metrics

Monitor these key metrics:

- `schedules_due`: Number of schedules due for execution
- `runs_emitted`: Number of workflow runs started
- `runs_skipped_overlap`: Runs skipped due to overlap policy
- `runs_failed_launch`: Failed workflow launches

## Contributing

1. Follow the existing code style and patterns
2. Add comprehensive error handling
3. Include logging for debugging
4. Write tests for new functionality
5. Update documentation for API changes
6. Consider backward compatibility

## License

This project is part of the workflow automation engine.
