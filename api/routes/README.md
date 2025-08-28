# API Routes Structure

This directory contains all the API route modules organized by functionality. Each route file handles specific endpoints and is organized into logical categories.

## 📁 Directory Structure

```
routes/
├── __init__.py                    # Main routes package - combines all routers
├── system.py                      # System-level routes (health checks)
├── frontend/                      # Frontend-specific routes
│   ├── __init__.py               # Frontend package - combines frontend routers
│   ├── integrations.py           # Integration management
│   ├── suggestions.py            # Workflow suggestions
│   └── preferences.py            # User preferences
├── runs/                         # Workflow execution runs
│   ├── __init__.py               # Runs package - combines run routers
│   ├── execution.py              # Run creation & execution (currently mock)
│   └── monitoring.py             # Run monitoring & status (currently mock)
├── catalog/                      # Tool catalog management
│   ├── __init__.py               # Catalog package - combines catalog routers
│   ├── providers.py              # Provider information
│   └── tools.py                  # Tool information & search
└── auth/                         # Authentication & sessions
    ├── __init__.py               # Auth package - combines auth routers
    └── auth.py                   # Auth endpoints (testing only)
```

## 🎯 Route File Purposes

### **Root Level Files**
- **`__init__.py`** - Main routes package that combines all routers
- **`system.py`** - System health and status endpoints

### **Frontend Routes** (`/api/*`)
- **`integrations.py`** - Available integrations for the UI
- **`suggestions.py`** - Generate workflow suggestions
- **`preferences.py`** - User preferences and settings

### **Run Routes** (`/runs/*`)
- **`execution.py`** - Create and execute workflow runs (currently mock)
- **`monitoring.py`** - List runs, get run details, stream updates (currently mock)

### **Catalog Routes** (`/catalog/*`)
- **`providers.py`** - Get provider information and metadata
- **`tools.py`** - Search and browse available tools

### **Auth Routes** (`/auth/*`)
- **`auth.py`** - User authentication and sessions (testing only)

## 🔗 Endpoint Mapping

| Endpoint | Route File | Purpose | Status |
|----------|------------|---------|---------|
| `GET /health` | `system.py` | System health check | ✅ Implemented |
| `GET /api/integrations` | `frontend/integrations.py` | List available integrations | ✅ Implemented |
| `POST /api/suggestions:generate` | `frontend/suggestions.py` | Generate frontend suggestions | ✅ Implemented |
| `GET /api/preferences/{user_id}` | `frontend/preferences.py` | Get user preferences | ✅ Implemented |
| `GET /auth/session` | `auth/auth.py` | Get auth session | ⚠️ Testing only |
| `POST /auth/login` | `auth/auth.py` | User login | ⚠️ Testing only |
| `POST /runs` | `runs/execution.py` | Create workflow run | ⚠️ Mock data |
| `GET /runs` | `runs/monitoring.py` | List workflow runs | ⚠️ Mock data |
| `GET /runs/{id}` | `runs/monitoring.py` | Get run details | ⚠️ Mock data |
| `GET /runs/stream` | `runs/monitoring.py` | Stream updates | ❌ Not implemented |
| `GET /catalog/providers/{slug}` | `catalog/providers.py` | Get provider info | ✅ Implemented |
| `GET /catalog/tools` | `catalog/tools.py` | List/search tools | ✅ Implemented |
| `GET /catalog/tools/{name}` | `catalog/tools.py` | Get tool details | ✅ Implemented |

## 🧹 Cleanup Recommendations

### **Files That Can Be Removed:**
None - all current files are actively used.

### **Files That Could Be Consolidated:**
1. **Run execution** + **Run monitoring** - Could be one file if simple
2. **Catalog providers** + **Catalog tools** - Could be one file if small

### **Keep These (Well Organized):**
- **`frontend/`** folder structure - Good separation of concerns
- **`runs/`** folder structure - Clear execution vs monitoring split
- **`catalog/`** folder structure - Provider vs tool separation
- **`auth/`** folder structure - Authentication separation

## 📝 Adding New Routes

1. **Identify the category** (frontend, runs, catalog, auth, etc.)
2. **Create a new file** in the appropriate subfolder
3. **Define the router** with proper tags
4. **Import and include** in the package `__init__.py`
5. **Update this README** with the new route information

## 🔧 Development Workflow

1. **Modify existing routes** in their specific files
2. **Add new endpoints** to existing route files or create new ones
3. **Test individual route files** in isolation
4. **Import changes** are automatically handled by the package structure
5. **Main app** automatically gets all route updates

## 🚧 Current Limitations

### **Mock Implementations**
- Run execution endpoints return fake data
- Run monitoring shows mock run history
- No real workflow execution integration

### **Missing Features**
- Workflow planning endpoints
- Workflow CRUD operations
- Workflow lifecycle management
- Real-time execution monitoring
- Proper state persistence

## 🔮 Future Improvements

1. **Integrate with executor service** for real workflow execution
2. **Add workflow management endpoints**
3. **Implement real-time monitoring** with WebSockets/SSE
4. **Add proper database integration** for persistence
5. **Implement real authentication** beyond testing
6. **Add comprehensive error handling** and validation
