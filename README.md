# Weave - Workflow Automation Engine UI

A modern, responsive web interface for building and managing automated workflows. Built with FastAPI, Jinja2 templates, HTMX, and TailwindCSS.

## Features

- **Home Page**: Describe what you want to automate and select integrations
- **Workflow Suggestions**: AI-powered workflow recommendations based on your prompt
  - **Multiple Suggestions**: Generate 1-5 workflow options in parallel for variety and choice
- **Workflow Builder**: Visual workflow editor with drag-and-drop nodes
- **Real-time Logs**: Live execution monitoring and debugging
- **Integration Management**: Connect and manage various service integrations
- **Catalog System**: Comprehensive provider, action, and trigger catalog with caching
- **Responsive Design**: Works seamlessly on desktop and mobile devices

## Tech Stack

- **Backend**: FastAPI (Python)
- **Templates**: Jinja2
- **Frontend**: HTMX + Alpine.js + TailwindCSS
- **HTTP Client**: httpx for backend API communication
- **Authentication**: Email-based magic link authentication

## Project Structure

```
app/
├── main.py              # FastAPI application entry point
├── ui_routes.py         # UI routes and HTMX partials
├── services/
│   └── ui_client.py     # HTTP client for backend APIs
└── templates/
    ├── base.html        # Base template with common layout
    ├── components/      # Reusable UI components
    ├── pages/          # Main page templates
    └── partials/       # HTMX partial templates

core/
├── catalog/             # Catalog system (providers, actions, triggers)
│   ├── models.py        # Data models
│   ├── fetchers.py      # Data source fetchers
│   ├── database_service.py # Main database service
│   └── cache.py         # Redis cache store
└── dsl/                 # Domain-specific language definitions

database/
├── config.py            # Database configuration
└── schema/              # Database schemas
    ├── catalog_tables.sql
    └── user_tables.sql

scripts/
├── catalog/             # Catalog management scripts
│   ├── fetch_categories.py
│   ├── fetch_all_tools.py
│   └── ...
└── setup_catalog.py     # Catalog setup script
```

## Prerequisites

- Python 3.8+
- Virtual environment (recommended)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd workflow-automation-engine
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables**
   ```bash
   export WEAVE_API_BASE=http://localhost:8001  # Backend API URL
   export COMPOSIO_API_KEY=your_composio_api_key_here  # For catalog data
   export DATABASE_URL=postgresql://user:password@localhost/workflow_automation
   export REDIS_URL=redis://localhost:6379
   ```

## Running the Application

### Option 1: Start Both Servers (Recommended)
```bash
python start_both.py
```

This will start both the frontend (port 8000) and backend (port 8001) servers.

### Option 2: Start Servers Separately

**Start Backend API:**
```bash
cd api
python run.py
```
Backend will be available at `http://localhost:8001`

**Start Frontend UI:**
```bash
python run.py
```
Frontend will be available at `http://localhost:8000`

### Open Your Browser
Navigate to `http://localhost:8000` for the UI

## Catalog System

The project includes a comprehensive catalog system for managing providers, actions, and triggers. This system provides:

- **Provider Management**: Store and retrieve information about service providers (Gmail, Slack, etc.)
- **Action Specifications**: Define available actions for each provider
- **Trigger Specifications**: Define available triggers for each provider
- **Caching**: Redis-based caching for performance
- **Database Storage**: PostgreSQL-based persistent storage

### Setting Up the Catalog

1. **Run the setup script:**
   ```bash
   python scripts/setup_catalog.py
   ```

2. **Or set up manually:**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Set up database
   createdb workflow_automation
   psql -d workflow_automation -f database/schema/catalog_tables.sql
   
   # Start Redis
   brew services start redis  # macOS
   
   # Test setup
   python scripts/catalog/test_catalog_setup.py
   ```

3. **Populate with data:**
   ```bash
   python scripts/catalog/fetch_categories.py
   python scripts/catalog/update_categories_local.py
   python scripts/catalog/fetch_all_toolkits_fixed.py
   python scripts/catalog/update_toolkits_final.py
   python scripts/catalog/fetch_all_tools.py
   ```

For detailed information, see [Catalog Migration Guide](docs/CATALOG_MIGRATION_GUIDE.md).

## Development

### Backend API Requirements

The UI expects a backend API with the following endpoints:

- `GET /api/integrations` - List available integrations
- `POST /api/suggestions:generate` - Generate workflow suggestions
- `GET /api/preferences/{user_id}` - Get user preferences
- `GET /api/auth/session`# super-enigma
