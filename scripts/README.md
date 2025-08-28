# Catalog System Scripts

This directory contains scripts for setting up and managing the catalog system.

## Quick Start

1. **Set up environment variables:**
   ```bash
   export COMPOSIO_API_KEY=your_composio_api_key_here
   export DATABASE_URL=postgresql://user:password@localhost/workflow_automation
   export REDIS_URL=redis://localhost:6379
   ```

2. **Run the setup script:**
   ```bash
   python scripts/setup_catalog.py
   ```

3. **Test the setup:**
   ```bash
   python scripts/catalog/test_catalog_setup.py
   ```

## Scripts

- **`setup_catalog.py`** - Main setup script that guides you through the entire process
- **`catalog/test_catalog_setup.py`** - Test script to verify the catalog system is working

## What the Setup Script Does

1. Checks environment variables
2. Installs Python dependencies
3. Sets up PostgreSQL database
4. Sets up Redis
5. Applies database schema

## Prerequisites

- Python 3.8+
- PostgreSQL
- Redis
- Composio API key

## Troubleshooting

If you encounter issues:

1. Make sure all environment variables are set
2. Ensure PostgreSQL and Redis are running
3. Check that you're in the project root directory
4. Verify all dependencies are installed

For more detailed information, see `docs/CATALOG_MIGRATION_GUIDE.md`
