# Test Suite for Workflow Automation Engine

This directory contains comprehensive tests for the workflow automation engine, covering all major components including APIs, services, and core modules.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Pytest configuration and fixtures
├── README.md                   # This file
├── requirements-test.txt        # Test dependencies
├── run_tests.py                # Test runner script
├── test_api_main.py              # Main API tests
├── test_api_integrations.py      # Integration API tests
├── test_api_suggestions.py       # Suggestions API tests
├── test_api_auth.py              # Authentication API tests
├── test_api_preferences.py       # Preferences API tests
├── test_services_executor.py   # Executor service tests
├── test_services_scheduler.py  # Scheduler service tests
├── test_core_config.py         # Core configuration tests
├── test_core_catalog.py        # Core catalog service tests
└── test_core_validator.py      # Core validator tests
```

## Test Coverage

The test suite provides comprehensive coverage for:

### 🚀 **API Layer**
- **Main Application**: FastAPI app configuration, middleware, routing
- **Workflow Routes**: CRUD operations, lifecycle management, execution
- **Frontend Routes**: Authentication, integrations, preferences, suggestions
- **System Routes**: Health checks, system information
- **Catalog Routes**: Tool and trigger management
- **Planning Routes**: Workflow planning and optimization

### ⚙️ **Services Layer**
- **Executor Service**: Workflow execution engine, node management, state handling
- **Scheduler Service**: Cron scheduling, task management, run launching

### 🔧 **Core Layer**
- **Configuration**: Environment variables, settings management
- **Catalog**: Tool/trigger management, caching, database operations
- **Validator**: Schema validation, workflow validation, DSL validation

## Getting Started

### Prerequisites

1. **Python Environment**: Ensure you have Python 3.8+ installed
2. **Virtual Environment**: Activate your project's virtual environment
3. **Dependencies**: Install test dependencies

### Installation

```bash
# Navigate to your project directory
cd workflow-automation-engine

# Activate virtual environment (if using one)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install test dependencies
pip install -r tests/requirements-test.txt
```

### Running Tests

#### Quick Start
```bash
# Run all tests with coverage
python tests/run_tests.py

# Run tests without coverage
python tests/run_tests.py --no-coverage

# Run tests in parallel
python tests/run_tests.py --parallel
```

#### Specific Test Types
```bash
# Run only unit tests
python tests/run_tests.py --type unit

# Run only API tests
python tests/run_tests.py --type api

# Run only service tests
python tests/run_tests.py --type services

# Run only core module tests
python tests/run_tests.py --type core
```

#### Individual Test Files
```bash
# Run a specific test file
python tests/run_tests.py --file test_api_workflows.py

# Run tests for a specific component
python -m pytest tests/test_services_executor.py -v
```

#### Coverage Reports
```bash
# Generate coverage report only
python tests/run_tests.py --coverage-only

# Run tests and generate HTML coverage report
python -m pytest --cov=. --cov-report=html
```

### Using pytest Directly

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_core_config.py

# Run tests matching a pattern
pytest -k "test_config"

# Run tests in parallel
pytest -n auto
```

## Test Categories

### 🔍 **Unit Tests** (`@pytest.mark.unit`)
- Test individual functions and methods in isolation
- Mock external dependencies
- Fast execution
- High reliability

### 🔗 **Integration Tests** (`@pytest.mark.integration`)
- Test component interactions
- Use test databases and services
- Slower execution
- Test real workflows

### 🌐 **API Tests** (`@pytest.mark.api`)
- Test HTTP endpoints
- Validate request/response formats
- Test authentication and authorization
- Use FastAPI TestClient

### ⚡ **Service Tests** (`@pytest.mark.services`)
- Test business logic services
- Mock external APIs
- Test error handling
- Validate service contracts

### 🧠 **Core Tests** (`@pytest.mark.core`)
- Test configuration and utilities
- Test validation logic
- Test core data structures
- High coverage requirements

## Test Fixtures

The `conftest.py` file provides common fixtures:

### 🔧 **Application Fixtures**
- `test_client`: FastAPI TestClient instance
- `async_client`: Async HTTP client for async endpoints
- `mock_settings`: Mocked application settings

### 🗄️ **Database Fixtures**
- `test_db_engine`: In-memory SQLite database
- `test_db_session`: Database session for testing

### 🔌 **Service Fixtures**
- `mock_redis`: Mocked Redis client
- `mock_composio_client`: Mocked Composio API client
- `mock_database`: Mocked database session

### 📊 **Data Fixtures**
- `sample_workflow_data`: Sample workflow for testing
- `sample_execution_data`: Sample execution data
- `sample_catalog_data`: Sample catalog data

## Writing Tests

### Test Naming Convention
```python
def test_function_name_scenario():
    """Test description."""
    # Test implementation
```

### Test Class Naming Convention
```python
class TestComponentName:
    """Test the ComponentName class/functionality."""
    
    def test_method_name_scenario(self):
        """Test description."""
        # Test implementation
```

### Using Fixtures
```python
def test_workflow_creation(test_client, sample_workflow_data):
    """Test workflow creation endpoint."""
    response = test_client.post("/workflows", json=sample_workflow_data)
    assert response.status_code == 201
```

### Mocking External Dependencies
```python
@patch('services.executor.executor.ComposioClient')
def test_executor_with_mock_composio(mock_composio):
    """Test executor with mocked Composio client."""
    mock_composio.return_value.fetch_tool.return_value = {"tool": "data"}
    # Test implementation
```

### Async Tests
```python
@pytest.mark.asyncio
async def test_async_operation(async_client):
    """Test async operation."""
    response = await async_client.get("/async-endpoint")
    assert response.status_code == 200
```

## Test Data Management

### Sample Data
- Use fixtures for consistent test data
- Keep test data minimal and focused
- Use realistic but simple examples

### Database Testing
- Use in-memory SQLite for unit tests
- Use test databases for integration tests
- Clean up test data after each test

### Mock Data
- Mock external API responses
- Use consistent mock data across tests
- Validate mock data structure

## Coverage Goals

### Target Coverage: 80%+
- **Core Modules**: 90%+
- **API Routes**: 85%+
- **Services**: 80%+
- **Utilities**: 75%+

### Coverage Reports
```bash
# Generate HTML coverage report
pytest --cov=. --cov-report=html

# View coverage in terminal
pytest --cov=. --cov-report=term-missing

# Coverage report with fail threshold
pytest --cov=. --cov-fail-under=80
```

## Continuous Integration

### GitHub Actions
Tests run automatically on:
- Pull requests
- Push to main branch
- Scheduled runs

### Pre-commit Hooks
```bash
# Install pre-commit hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## Troubleshooting

### Common Issues

#### Import Errors
```bash
# Ensure you're in the project root
cd workflow-automation-engine

# Check Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### Missing Dependencies
```bash
# Install test requirements
pip install -r tests/requirements-test.txt

# Check installed packages
pip list | grep pytest
```

#### Database Connection Issues
```bash
# Use in-memory database for tests
export DATABASE_URL="sqlite:///:memory:"

# Check database configuration
python -c "from core.config import settings; print(settings.database_url)"
```

#### Redis Connection Issues
```bash
# Mock Redis for tests
export REDIS_URL="redis://localhost:6379"

# Or use mock in tests
@patch('core.catalog.cache.redis.Redis')
def test_with_mock_redis(mock_redis):
    # Test implementation
```

### Debug Mode
```bash
# Run tests with debug output
pytest -v -s --tb=long

# Run single test with debug
pytest tests/test_core_config.py::TestSettings::test_default_values -v -s
```

## Best Practices

### ✅ **Do**
- Write descriptive test names
- Use appropriate assertions
- Mock external dependencies
- Clean up test data
- Test both success and failure cases
- Use fixtures for common setup

### ❌ **Don't**
- Test implementation details
- Create complex test data
- Make tests dependent on each other
- Use real external services
- Skip error handling tests
- Ignore test failures

## Contributing

### Adding New Tests
1. Create test file following naming convention
2. Add appropriate test markers
3. Use existing fixtures when possible
4. Ensure good test coverage
5. Update this README if needed

### Test Review Checklist
- [ ] Tests are descriptive and clear
- [ ] Appropriate use of fixtures
- [ ] Good coverage of edge cases
- [ ] Proper mocking of dependencies
- [ ] Tests are independent
- [ ] Error cases are tested

## Support

For questions about the test suite:
1. Check this README
2. Review existing test examples
3. Check pytest documentation
4. Open an issue for bugs
5. Ask in team discussions

---

**Happy Testing! 🧪✨**
