# Catalog System Migration Guide

This guide explains how to set up and use the catalog system that has been migrated to this project.

## 📋 Overview

The catalog system provides:
- **Provider Management**: Store and retrieve information about service providers (Gmail, Slack, etc.)
- **Action Specifications**: Define available actions for each provider
- **Trigger Specifications**: Define available triggers for each provider
- **Caching**: Redis-based caching for performance
- **Database Storage**: PostgreSQL-based persistent storage
- **API Integration**: Composio API integration for fetching catalog data

## 🚀 Quick Setup

### 1. Install Dependencies

First, install the required dependencies:

```bash
# Activate your virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Set Environment Variables

Set the required environment variables:

```bash
# Composio API (required for fetching catalog data)
export COMPOSIO_API_KEY=your_composio_api_key_here

# Database (PostgreSQL)
export DATABASE_URL=postgresql://user:password@localhost/workflow_automation

# Redis
export REDIS_URL=redis://localhost:6379
```

### 3. Set Up Database

Create the database and run the schema:

```bash
# Create database (if it doesn't exist)
createdb workflow_automation

# Run the catalog schema
psql -d workflow_automation -f database/schema/catalog_tables.sql
```

### 4. Start Redis

Ensure Redis is running:

```bash
# macOS
brew services start redis

# Linux
sudo systemctl start redis

# Test connection
redis-cli ping
```

### 5. Test the Setup

Run the test script to verify everything is working:

```bash
python scripts/catalog/test_catalog_setup.py
```

## 📊 Populating the Catalog

Once the setup is complete, populate the catalog with data:

### Step 1: Fetch Categories
```bash
python scripts/catalog/fetch_categories.py
```

### Step 2: Update Categories in Database
```bash
python scripts/catalog/update_categories_local.py
```

### Step 3: Fetch Toolkits
```bash
python scripts/catalog/fetch_all_toolkits_fixed.py
```

### Step 4: Update Toolkits in Database
```bash
python scripts/catalog/update_toolkits_final.py
```

### Step 5: Fetch Tools
```bash
python scripts/catalog/fetch_all_tools.py
```

## 🏗️ Architecture

### Core Components

```
core/catalog/
├── models.py             # Data models (Provider, ActionSpec, etc.)
├── fetchers.py           # Data source fetchers (Composio API)
├── database_service.py   # Main database service
├── cache.py              # Redis cache store
├── redis_client.py       # Redis connection factory
├── service.py            # Basic service interface
└── __init__.py           # Package exports
```

### Database Schema

The catalog uses these main tables:
- `providers`: Service providers (Gmail, Slack, etc.)
- `provider_metadata`: Additional provider information
- `action_specs`: Available actions for each provider
- `trigger_specs`: Available triggers for each provider
- `param_specs`: Parameter definitions for actions/triggers

### Caching Strategy

- **Redis Cache**: Performance cache with 1-hour TTL
- **Database**: Primary data store
- **External APIs**: Source of truth for fresh data

## 🔧 Usage Examples

### Basic Usage

```python
from core.catalog import DatabaseCatalogService, RedisCacheStore, RedisClientFactory

# Initialize services
redis_client = RedisClientFactory.create_client()
cache_store = RedisCacheStore(redis_client)
catalog_service = DatabaseCatalogService(database_url, cache_store)

# Get catalog data
catalog = await catalog_service.get_catalog()
```

### Filtering Providers

```python
# Get only Gmail provider
gmail_data = await catalog_service.get_catalog(providers=["gmail"])

# Get providers with actions
providers_with_actions = await catalog_service.get_catalog(has_actions=True)

# Get providers with triggers
providers_with_triggers = await catalog_service.get_catalog(has_triggers=True)
```

### Force Refresh

```python
# Force refresh from external sources
fresh_data = await catalog_service.get_catalog(force_refresh=True)
```

## 🔍 API Endpoints

The catalog system can be exposed via FastAPI endpoints. Example:

```python
from fastapi import FastAPI, Depends
from core.catalog import DatabaseCatalogService

app = FastAPI()

@app.get("/catalog")
async def get_catalog(
    providers: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    catalog_service: DatabaseCatalogService = Depends(get_catalog_service)
):
    return await catalog_service.get_catalog(providers=providers, categories=categories)
```

## 🛠️ Maintenance

### Updating Catalog Data

The catalog data can be refreshed periodically:

```bash
# Refresh all data
python scripts/catalog/update_catalog_refresh_job.py
```

### Monitoring

Check the health of the catalog system:

```bash
# Test Redis cache
python scripts/catalog/test_redis_cache.py

# Test database connection
python scripts/catalog/debug_database.py
```

## 🚨 Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure all dependencies are installed
   - Check Python path includes project root

2. **Database Connection Issues**
   - Verify PostgreSQL is running
   - Check DATABASE_URL format
   - Ensure database exists

3. **Redis Connection Issues**
   - Verify Redis is running
   - Check REDIS_URL format

4. **API Key Issues**
   - Verify COMPOSIO_API_KEY is set
   - Check API key validity

### Debug Commands

```bash
# Test basic connectivity
python scripts/catalog/quick_test.py

# Test environment setup
python scripts/catalog/test_env.py

# Debug database
python scripts/catalog/debug_database.py
```

## 📚 Additional Resources

- `scripts/catalog/README.md`: Detailed script documentation
- `scripts/catalog/SETUP_GUIDE.md`: Step-by-step setup guide
- `scripts/catalog/EXECUTION_GUIDE.md`: Execution workflow guide
- `core/catalog/README.md`: Core catalog documentation

## 🔄 Migration Notes

This catalog system was migrated from another project. Key changes made:

1. **Configuration**: Updated to use `core.config` settings
2. **Dependencies**: Added to main `requirements.txt`
3. **Import Paths**: Updated to match new project structure
4. **Database Schema**: Copied and ready to use
5. **Scripts**: All utility scripts included and functional

The system is designed to be modular and should work as a standalone component within this project.
