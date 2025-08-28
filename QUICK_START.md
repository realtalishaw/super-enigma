# Quick Start Guide

## Getting Both Servers Running

The Weave workflow automation engine requires **two separate servers** to be running:

1. **Backend API Server** (Port 8001) - Provides integrations, workflow generation, and core functionality
2. **Frontend UI Server** (Port 8000) - Provides the web interface

## Option 1: Start Both Servers (Recommended)

Use the provided script to start both servers simultaneously:

```bash
python start_both.py
```

This will:
- Start the backend API on port 8001
- Start the frontend UI on port 8000
- Show real-time logs from both servers
- Automatically stop both when you press Ctrl+C

## Option 2: Start Servers Separately

### Start Backend API Server
```bash
cd api
python run.py
```
The backend will start on port 8001.

### Start Frontend UI Server (in a new terminal)
```bash
python run.py
```
The frontend will start on port 8000.

## Verify Both Servers Are Running

### Backend API (Port 8001)
```bash
curl http://localhost:8001/health
```
Should return: `{"status": "healthy", "service": "weave-api"}`

### Frontend UI (Port 8000)
```bash
curl http://localhost:8000/health
```
Should return: `{"status": "healthy", "service": "weave-ui"}`

## Access the Application

- **Frontend UI**: http://localhost:8000
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs

## Why Two Servers?

- **Backend API**: Handles database operations, workflow generation, and core business logic
- **Frontend UI**: Provides the web interface and communicates with the backend API
- **Separation of Concerns**: Allows independent scaling and development of each component

## Troubleshooting

### "No integrations available" error
This means the backend API server is not running or not accessible. Ensure:
1. Backend server is running on port 8001
2. No firewall blocking the connection
3. Check backend server logs for errors

### "Cannot connect to backend API" error
The frontend cannot reach the backend. Check:
1. Backend server is running
2. Port 8001 is not blocked
3. Network configuration allows localhost connections

### Port already in use
If you get "port already in use" errors:
1. Check what's using the port: `lsof -i :8001` or `lsof -i :8000`
2. Stop the conflicting process
3. Or change ports in the configuration files

## Environment Variables

Set these if you need to customize the setup:

```bash
export WEAVE_API_BASE=http://localhost:8001  # Backend API URL
export WEAVE_FRONTEND_PORT=8000              # Frontend port
export WEAVE_BACKEND_PORT=8001               # Backend port
```

## Next Steps

Once both servers are running:
1. Visit http://localhost:8000
2. Enter a workflow prompt
3. Select integrations
4. Click "Get Suggestions" to generate workflows
5. View and interact with the generated suggestions
