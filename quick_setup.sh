#!/bin/bash

# Quick Setup Script for Workflow Automation Engine
# This script provides a fast way to get the system running

set -e  # Exit on any error

echo "🚀 Workflow Automation Engine - Quick Setup"
echo "============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ️${NC} $1"
}

# Check if Python 3.9+ is available
check_python() {
    print_info "Checking Python version..."
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if python3 -c 'import sys; exit(0 if sys.version_info >= (3, 9) else 1)'; then
            print_status "Python $PYTHON_VERSION found"
            PYTHON_CMD="python3"
        else
            print_error "Python 3.9+ required, found $PYTHON_VERSION"
            exit 1
        fi
    elif command -v python &> /dev/null; then
        PYTHON_VERSION=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if python -c 'import sys; exit(0 if sys.version_info >= (3, 9) else 1)'; then
            print_status "Python $PYTHON_VERSION found"
            PYTHON_CMD="python"
        else
            print_error "Python 3.9+ required, found $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python not found. Please install Python 3.9+"
        exit 1
    fi
}

# Check if virtual environment exists
check_venv() {
    if [ -d "venv" ]; then
        print_status "Virtual environment exists"
        return 0
    else
        print_info "Creating virtual environment..."
        $PYTHON_CMD -m venv venv
        print_status "Virtual environment created"
    fi
}

# Activate virtual environment
activate_venv() {
    print_info "Activating virtual environment..."
    source venv/bin/activate
    print_status "Virtual environment activated"
}

# Install dependencies
install_deps() {
    print_info "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    print_status "Dependencies installed"
}

# Check if .env file exists
check_env() {
    if [ -f ".env" ]; then
        print_status "Environment file exists"
    else
        print_warning "Environment file not found"
        print_info "Creating .env file with defaults..."
        
        cat > .env << EOF
# Workflow Automation Engine Environment Variables
DATABASE_URL=mongodb+srv://dylan:43VFMVJVJUFAII9g@cluster0.8phbhhb.mongodb.net/weave-dev-db?retryWrites=true&w=majority
REDIS_URL=redis://localhost:6379
COMPOSIO_API_KEY=your_composio_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GROQ_API_KEY=your_groq_api_key_here
COMPOSIO_BASE_URL=https://api.composio.dev
DEBUG=false
LOG_LEVEL=INFO
SCHEDULER_URL=http://localhost:8003
WEAVE_API_BASE=http://localhost:8001
API_HOST=0.0.0.0
API_PORT=8001
EOF
        
        print_status "Environment file created"
        print_warning "Please update API keys in .env file before running the application"
    fi
}

# Check Redis
check_redis() {
    print_info "Checking Redis connection..."
    if command -v redis-cli &> /dev/null; then
        if redis-cli ping &> /dev/null; then
            print_status "Redis is running"
        else
            print_warning "Redis is not running"
            print_info "To start Redis:"
            print_info "  macOS: brew services start redis"
            print_info "  Linux: sudo systemctl start redis"
        fi
    else
        print_warning "Redis CLI not found"
        print_info "Please install Redis:"
        print_info "  macOS: brew install redis"
        print_info "  Linux: sudo apt-get install redis-server"
    fi
}

# Set up database
setup_database() {
    print_info "Setting up database..."
    if $PYTHON_CMD scripts/migrate_to_mongodb.py; then
        print_status "Database setup completed"
    else
        print_warning "Database setup failed - this may be due to network issues"
        print_info "The application may still work with limited functionality"
    fi
}

# Test setup
test_setup() {
    print_info "Testing setup..."
    if $PYTHON_CMD scripts/catalog/test_catalog_setup.py; then
        print_status "Setup test passed"
    else
        print_warning "Setup test failed - check your configuration"
    fi
}

# Create startup script
create_startup_script() {
    if [ ! -f "start_both.py" ]; then
        print_info "Creating startup script..."
        
        cat > start_both.py << 'EOF'
#!/usr/bin/env python3
"""
Start both frontend and backend servers.
"""

import subprocess
import sys
import time
import signal
import os
from pathlib import Path

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n🛑 Shutting down servers...")
    sys.exit(0)

def main():
    """Start both servers."""
    signal.signal(signal.SIGINT, signal_handler)
    
    project_root = Path(__file__).parent
    venv_python = project_root / "venv" / "bin" / "python"
    
    if os.name == 'nt':  # Windows
        venv_python = project_root / "venv" / "Scripts" / "python"
    
    print("🚀 Starting Workflow Automation Engine...")
    print("📡 Backend API: http://localhost:8001")
    print("🌐 Frontend UI: http://localhost:8000")
    print("📚 API Docs: http://localhost:8001/docs")
    print("\nPress Ctrl+C to stop both servers\n")
    
    try:
        # Start backend
        backend_process = subprocess.Popen([
            str(venv_python), "api/run.py"
        ], cwd=project_root)
        
        # Wait a moment for backend to start
        time.sleep(3)
        
        # Start frontend (if it exists)
        frontend_script = project_root / "run.py"
        if frontend_script.exists():
            frontend_process = subprocess.Popen([
                "python", "run.py"
            ], cwd=project_root)
        else:
            print("⚠️  Frontend script not found, only backend will start")
            frontend_process = None
        
        # Wait for processes
        try:
            backend_process.wait()
        except KeyboardInterrupt:
            pass
        finally:
            if frontend_process:
                frontend_process.terminate()
            backend_process.terminate()
            
    except Exception as e:
        print(f"❌ Error starting servers: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF
        
        chmod +x start_both.py
        print_status "Startup script created"
    else
        print_status "Startup script already exists"
    fi
}

# Main setup function
main() {
    echo
    check_python
    check_venv
    activate_venv
    install_deps
    check_env
    check_redis
    setup_database
    test_setup
    create_startup_script
    
    echo
    echo "🎉 Quick setup completed!"
    echo
    echo "📋 Next steps:"
    echo "1. Update API keys in .env file:"
    echo "   - COMPOSIO_API_KEY (required)"
    echo "   - ANTHROPIC_API_KEY (required)"
    echo "   - GROQ_API_KEY (optional)"
    echo
    echo "2. Start the application:"
    echo "   python api/run.py"
    echo
    echo "3. Access the application:"
    echo "   - Backend API: http://localhost:8001"
    echo "   - API Docs: http://localhost:8001/docs"
    echo
    echo "📚 For detailed setup, run: python setup.py"
    echo "📖 For documentation, see: HANDOFF_DOCUMENTATION.md"
    echo
}

# Run main function
main "$@"
