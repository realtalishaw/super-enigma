# API Structure

This directory contains the refactored API with separated concerns and organized route modules.

## Structure

```
api/
├── main.py                 # Main FastAPI application
├── models.py               # Centralized Pydantic models
├── cache_service.py        # Global cache service for integrations
├── routes/                 # Route modules organized by functionality
│   ├── __init__.py        # Routes package initialization
│   ├── system.py          # System routes (health checks)
│   ├── frontend/          # Frontend-specific routes
│   │   ├── __init__.py    # Frontend package initialization
│   │   ├── integrations.py # Integration management
│   │   ├── suggestions.py # Workflow suggestions
│   │   └── preferences.py # User preferences
│   ├── runs/              # Workflow execution runs
│   │   ├── __init__.py    # Runs package initialization
│   │   ├── execution.py   # Run creation & execution (currently mock)
│   │   └── monitoring.py  # Run monitoring & status (currently mock)
│   ├── catalog/           # Tool catalog management
│   │   ├── __init__.py    # Catalog package initialization
│   │   ├── providers.py   # Provider information
│   │   └── tools.py       # Tool information & search
│   └── auth/              # Authentication & sessions
│       ├── __init__.py    # Auth package initialization
│       └── auth.py        # Auth endpoints (testing only)
├── user_services/         # User service modules
│   ├── __init__.py        # User services package
│   ├── suggestions_service.py # Workflow suggestion logic
│   └── user_service.py    # User management logic
└── README.md              # This file
```

## Route Categories

### System Routes (`/`)
- **Health Check**: `GET /health` - System health status

### Frontend Routes (`/api`)
- **Integrations**: `GET /api/integrations` - Available integrations
- **Suggestions**: `POST /api/suggestions:generate` - Generate workflow suggestions
- **Preferences**: `GET /api/preferences/{user_id}` - Get user preferences

### Run Routes (`/runs`)
- **Execution**: `POST /runs` - Create workflow run (currently mock)
- **Monitoring**: `GET /runs` - List workflow runs (currently mock)
- **Run Details**: `GET /runs/{run_id}` - Get run details (currently mock)
- **Streaming**: `GET /runs/stream` - Stream updates (not implemented)

### Catalog Routes (`/catalog`)
- **Providers**: `GET /catalog/providers/{slug}` - Get provider info
- **Tools**: `GET /catalog/tools` - List/search tools
- **Tool Details**: `GET /catalog/tools/{name}` - Get tool details

### Auth Routes (`/auth`)
- **Session**: `GET /auth/session` - Get auth session (testing only)
- **Login**: `POST /auth/login` - User login (testing only)

## How to Use

### Starting the API Server

```bash
# From the project root directory
uvicorn api.main:app --host 127.0.0.1 --port 8001 --reload
```

### Environment Variables Required

```bash
# Required for cache service
ANTHROPIC_API_KEY=your_anthropic_key
DATABASE_URL=your_database_url
REDIS_URL=your_redis_url

# Optional
API_PORT=8001
API_HOST=127.0.0.1
```

### API Documentation

Once the server is running:
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc
- **OpenAPI Schema**: http://localhost:8001/openapi.json

## Current Status

### ✅ Fully Implemented
- System health endpoints
- Frontend integration endpoints
- Workflow suggestion generation
- User preferences management
- Catalog provider and tool endpoints
- Cache service for integrations
- Authentication endpoints (testing only)

### ⚠️ Partially Implemented (Mock Data)
- Run execution endpoints (return mock data)
- Run monitoring endpoints (return mock data)

### ❌ Not Implemented
- Workflow planning endpoints
- Workflow CRUD operations
- Workflow lifecycle management
- Real workflow execution (needs integration with executor service)

## Integration Points

### Cache Service
The API uses a global cache service (`cache_service.py`) that:
- Preloads integration data from Composio
- Provides cached responses for catalog endpoints
- Manages cache health and status

### User Services
User-related logic is separated into `user_services/`:
- `suggestions_service.py`: Generates workflow suggestions using AI
- `user_service.py`: Manages user data and preferences

## Development Notes

### Adding New Endpoints
1. Create a new route file in the appropriate subfolder
2. Define the router with proper tags
3. Import and include in the package `__init__.py`
4. Update this README with the new endpoint information

### Route Organization
- **Frontend routes** (`/api/*`): UI-specific endpoints
- **System routes** (`/`): Health and status
- **Run routes** (`/runs/*`): Workflow execution
- **Catalog routes** (`/catalog/*`): Tool and provider information
- **Auth routes** (`/auth/*`): Authentication (currently testing only)

### Mock vs Real Implementation
Several endpoints currently return mock data:
- Run execution endpoints need integration with `services/executor/`
- Run monitoring needs real state store integration
- Workflow endpoints need to be implemented

## Next Steps

1. **Integrate real workflow execution** with the executor service
2. **Implement workflow CRUD operations**
3. **Add real-time run monitoring** with proper state management
4. **Replace mock data** with real database/storage integration
5. **Add proper error handling** and validation
6. **Implement real-time streaming** for run updates
