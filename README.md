# Workflow Automation Engine

A powerful API-based workflow automation platform that connects various services and APIs to create automated workflows. Built with FastAPI and MongoDB.

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Redis (local or cloud)
- MongoDB access (configured cloud instance)
- API keys for Composio, Anthropic, and optionally Groq

### Setup

**Option 1: Quick Setup**
```bash
./quick_setup.sh
```

**Option 2: Comprehensive Setup**
```bash
python setup.py
```

**Option 3: Manual Setup**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
python setup_env.py

# Configure API keys in .env file
# Set up database
python scripts/migrate_to_mongodb.py
```

### Running the Application

**Start the API Server:**
```bash
python api/run.py
```

### Access Points
- **API Server**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs

## 🏗️ Architecture

### Core Components

- **API Server** (Port 8001) - FastAPI backend with REST endpoints
- **DSL Generator** - AI-powered workflow generation
- **Catalog System** - Integration and tool management

### Technology Stack

- **Backend**: FastAPI, Python 3.9+
- **Database**: MongoDB (cloud instance)
- **Cache**: Redis
- **AI**: Anthropic Claude, Groq
- **Integrations**: Composio API

## ✨ Features

- **Workflow Builder**: Programmatic workflow creation via API
- **Service Integration**: Connect to 100+ services via Composio
- **AI-Powered Suggestions**: Intelligent workflow recommendations using Claude
- **Real-time Execution**: Monitor and manage workflow runs
- **User Management**: Multi-user support with preferences and history
- **API-First Design**: RESTful API for all operations
- **Advanced Flow Control**: IF/ELSE, loops, parallel execution

## Catalog System

The project includes a comprehensive catalog system for managing providers, actions, and triggers. This system provides:

- **Provider Management**: Store and retrieve information about service providers (Gmail, Slack, etc.)
- **Action Specifications**: Define available actions for each provider
- **Trigger Specifications**: Define available triggers for each provider
- **Caching**: Redis-based caching for performance
- **Database Storage**: MongoDB-based persistent storage

### Setting Up the Catalog

1. **Run the setup script:**
   ```bash
   python scripts/setup_catalog.py
   ```

2. **Or set up manually:**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Set up MongoDB
   # Ensure MongoDB is running and accessible
   
   # Start Redis
   brew services start redis  # macOS
   
   # Run migration script
   python scripts/migrate_to_mongodb.py
   
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
- `GET /api/auth/session` - Get authentication session
