# Workflow Automation Engine - Handoff Documentation

## Overview

The Workflow Automation Engine is a comprehensive platform for creating, managing, and executing automated workflows. It provides a visual workflow builder, AI-powered suggestions, and integration with 100+ services via Composio.

## Architecture

### Core Components

1. **API Server** (Port 8001) - FastAPI backend providing REST endpoints
2. **DSL Generator** - AI-powered workflow generation
3. **Catalog System** - Integration and tool management

### Technology Stack

- **Backend**: FastAPI, Python 3.9+
- **Database**: MongoDB (cloud instance)
- **Cache**: Redis
- **AI**: Anthropic Claude, Groq
- **Integrations**: Composio API

## Quick Setup

### Prerequisites

- Python 3.9+
- Node.js 18+
- Redis (local or cloud)
- MongoDB access (configured cloud instance)
- API keys for Composio, Anthropic, and optionally Groq

### Automated Setup

Run the comprehensive setup script:

```bash
python setup.py
```

This will:
- Create virtual environment
- Install all dependencies
- Set up environment variables
- Configure database
- Create startup scripts
- Verify all components

### Manual Setup

If you prefer manual setup:

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**
   ```bash
   export COMPOSIO_API_KEY=your_composio_api_key_here
   export ANTHROPIC_API_KEY=your_anthropic_api_key_here
   export DATABASE_URL=mongodb+srv://dylan:43VFMVJVJUFAII9g@cluster0.8phbhhb.mongodb.net/weave-dev-db?retryWrites=true&w=majority
   export REDIS_URL=redis://localhost:6379
   ```

4. **Set up database**
   ```bash
   python scripts/migrate_to_mongodb.py
   ```

5. **Test setup**
   ```bash
   python scripts/catalog/test_catalog_setup.py
   ```

## Running the Application

### Option 1: Start Everything (Recommended)

```bash
python start_both.py
```

This starts both frontend and backend servers.

### Option 2: Start Services Separately

**Backend API:**
```bash
python api/run.py
```

### Option 2: Start from API Directory

**API Server:**
```bash
cd api
python run.py
```

## Service Details

### API Server (Port 8001)

**Main Entry Point:** `api/main.py`
**Startup Script:** `api/run.py`

**Key Endpoints:**
- `GET /api/integrations/health` - Health check
- `GET /api/integrations/rate-limiting/status` - Rate limiting status
- `GET /api/integrations/ai-client/status` - AI client status
- `GET /api/integrations` - List available integrations
- `POST /api/suggestions:generate` - Generate workflow suggestions
- `GET /api/preferences/{user_id}` - Get user preferences
- `GET /api/auth/session` - Authentication session

**Route Modules:**
- `api/routes/api/` - Main API endpoints (integrations, suggestions, preferences, system health)
- `api/routes/catalog/` - Catalog management
- `api/routes/auth/` - Authentication

### DSL Generator

**Main Module:** `services/dsl_generator/generator.py`

**Features:**
- AI-powered workflow generation
- RAG (Retrieval-Augmented Generation) workflow
- Claude integration for intelligent suggestions
- Groq integration for fast tool retrieval

**Components:**
- `DSLGeneratorService` - Main orchestrator
- `CatalogManager` - Catalog data management
- `ContextBuilder` - Generation context
- `PromptBuilder` - Claude prompts
- `AIClient` - AI API interactions

### Catalog System

**Main Components:**
- `core/catalog/service.py` - Catalog service
- `core/catalog/database_service.py` - Database operations
- `core/catalog/cache.py` - Redis caching
- `core/catalog/fetchers.py` - Data fetching

**Collections:**
- `toolkits` - Service providers
- `tools` - Available actions
- `toolkit_categories` - Provider categories
- `users` - User management
- `user_preferences` - User settings

## Configuration

### Environment Variables

**Required:**
- `COMPOSIO_API_KEY` - Composio API key for integrations
- `ANTHROPIC_API_KEY` - Anthropic API key for Claude
- `DATABASE_URL` - MongoDB connection string
- `REDIS_URL` - Redis connection string

**Optional:**
- `GROQ_API_KEY` - Groq API key for fast tool retrieval
- `DEBUG` - Enable debug mode (default: false)
- `LOG_LEVEL` - Logging level (default: INFO)
- `API_PORT` - API server port (default: 8001)
- `SCHEDULER_URL` - Scheduler service URL (default: http://localhost:8003)

### Database Configuration

**MongoDB Collections:**
- `toolkits` - Service providers and metadata
- `tools` - Available actions and parameters
- `toolkit_categories` - Provider categories
- `users` - User accounts and preferences
- `user_preferences` - User-specific settings
- `suggestions` - Generated workflow suggestions

**Indexes:**
- Unique indexes on `slug` fields
- Performance indexes on `category`, `last_synced_at`
- User-specific indexes on `user_id`, `email`

## Development

### Project Structure

```
workflow-automation-engine/
├── api/                    # FastAPI backend
│   ├── main.py            # Main application
│   ├── run.py             # Startup script
│   ├── routes/            # API endpoints
│   ├── middleware/        # Request middleware
│   └── user_services/     # User management
├── core/                  # Core functionality
│   ├── config.py          # Configuration
│   ├── catalog/           # Catalog system
│   ├── dsl/               # DSL schemas
│   ├── logging_config.py  # Logging setup
│   └── validator/         # Validation tools
├── services/              # Microservices
│   ├── dsl_generator/     # AI workflow generation
│   ├── executor/          # Workflow execution
│   └── scheduler/         # Cron scheduling
├── scripts/               # Setup and utility scripts
├── docs/                  # Documentation
├── database/              # Database configuration
└── evals/                 # Evaluation reports
```

### Adding New Features

1. **API Endpoints**: Add to appropriate route module in `api/routes/`
2. **Database Models**: Update `core/catalog/models.py`
3. **Services**: Add to `services/` directory
4. **Frontend**: Update React components (if applicable)

### Testing

**Test Catalog Setup:**
```bash
python scripts/catalog/test_catalog_setup.py
```

**Test API Health:**
```bash
curl http://localhost:8001/health
```

**Test Scheduler:**
```bash
curl http://localhost:8003/health
```

## Troubleshooting

### Common Issues

1. **"No integrations available"**
   - Backend API server not running
   - Check port 8001 is accessible
   - Verify environment variables

2. **"Cannot connect to backend API"**
   - Backend server not started
   - Firewall blocking port 8001
   - Check backend logs for errors

3. **"Redis connection failed"**
   - Redis not running: `brew services start redis`
   - Check REDIS_URL environment variable

4. **"MongoDB connection failed"**
   - Verify DATABASE_URL is correct
   - Check network connectivity to MongoDB Atlas

5. **"API key errors"**
   - Verify COMPOSIO_API_KEY is set
   - Verify ANTHROPIC_API_KEY is set
   - Check API key validity

### Debug Mode

Enable debug logging:
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

### Logs

**API Server Logs:**
- Structured logging via `core/logging_config.py`
- Request/response logging via middleware

**Scheduler Logs:**
- Worker status and schedule execution
- Error handling and retries

**Executor Logs:**
- Workflow execution progress
- Node execution details
- Error tracking

## Production Considerations

### Security

- Update default API keys
- Use environment-specific configuration
- Enable HTTPS in production
- Implement proper authentication
- Add rate limiting

### Scaling

- Use production database (PostgreSQL/MySQL)
- Implement Redis clustering
- Add load balancing
- Use message queues for async processing
- Implement horizontal scaling

### Monitoring

- Add Prometheus metrics
- Implement health checks
- Set up alerting
- Monitor API performance
- Track workflow execution metrics

### Deployment

- Use Docker containers
- Implement CI/CD pipelines
- Use environment-specific configs
- Set up backup strategies
- Implement graceful shutdowns

## API Documentation

### Interactive Documentation

- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

### Key Endpoints

**System:**
- `GET /health` - Health check
- `GET /` - API information

**Integrations:**
- `GET /api/integrations` - List integrations
- `GET /api/integrations/{provider}` - Provider details

**Suggestions:**
- `POST /api/suggestions:generate` - Generate workflows
- `GET /api/suggestions/{suggestion_id}` - Get suggestion

**User Management:**
- `GET /api/preferences/{user_id}` - User preferences
- `POST /api/preferences/{user_id}` - Update preferences

**Authentication:**
- `GET /api/auth/session` - Get session
- `POST /api/auth/login` - Login
- `POST /api/auth/logout` - Logout

## Support and Maintenance

### Regular Tasks

1. **Monitor service health**
2. **Update API keys as needed**
3. **Review and rotate credentials**
4. **Monitor database performance**
5. **Check Redis memory usage**
6. **Review workflow execution logs**

### Backup Strategy

- **Database**: MongoDB Atlas automated backups
- **Configuration**: Version control in Git
- **Logs**: Centralized logging system
- **Code**: Git repository with tags

### Updates

- **Dependencies**: Regular security updates
- **API Keys**: Rotate periodically
- **Database**: Monitor for schema changes
- **Services**: Update microservices independently

## Contact and Resources

### Documentation

- `README.md` - Main project documentation
- `QUICK_START.md` - Quick start guide
- `docs/` - Detailed technical documentation
- `services/*/README.md` - Service-specific docs

### Scripts

- `setup.py` - Comprehensive setup script
- `scripts/setup_catalog.py` - Catalog setup
- `scripts/migrate_to_mongodb.py` - Database migration
- `scripts/catalog/test_catalog_setup.py` - Test setup

### Configuration Files

- `.env` - Environment variables
- `requirements.txt` - Python dependencies
- `core/config.py` - Application configuration
- `database/config.py` - Database configuration

---

**Last Updated:** January 2025
**Version:** 1.0.0
**Maintainer:** Development Team
