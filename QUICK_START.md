# Quick Start Guide

## Getting the API Server Running

The Weave workflow automation engine is an API-only service:

1. **Backend API Server** (Port 8001) - Provides integrations, workflow generation, and core functionality

## Option 1: Start the API Server (Recommended)

Start the API server directly:

```bash
python api/run.py
```

This will:
- Start the backend API on port 8001
- Show real-time logs from the server
- Automatically stop when you press Ctrl+C

## Option 2: Start from API Directory

### Start Backend API Server
```bash
cd api
python run.py
```
The backend will start on port 8001.

## Verify the API Server Is Running

### Backend API (Port 8001)
```bash
curl http://localhost:8001/health
```
Should return: `{"status": "healthy", "service": "weave-api"}`

## Access the Application

- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs

## API-Only Architecture

- **Backend API**: Handles database operations, workflow generation, and core business logic
- **RESTful Design**: All functionality accessible via API endpoints
- **API Documentation**: Interactive Swagger UI for testing and exploration

## Troubleshooting

### "No integrations available" error
This means the backend API server is not running or not accessible. Ensure:
1. Backend server is running on port 8001
2. No firewall blocking the connection
3. Check backend server logs for errors

### "Cannot connect to API" error
The API server is not accessible. Check:
1. API server is running
2. Port 8001 is not blocked
3. Network configuration allows localhost connections

### Port already in use
If you get "port already in use" errors:
1. Check what's using the port: `lsof -i :8001`
2. Stop the conflicting process
3. Or change ports in the configuration files

## Environment Variables

Set these if you need to customize the setup:

```bash
export WEAVE_API_BASE=http://localhost:8001  # Backend API URL
export WEAVE_BACKEND_PORT=8001               # Backend port
```

## Next Steps

Once the API server is running:
1. Visit http://localhost:8001/docs for interactive API documentation
2. Test the health endpoint: `curl http://localhost:8001/health`
3. Explore the available API endpoints
4. Use the API to create and manage workflows
