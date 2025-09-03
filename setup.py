#!/usr/bin/env python3
"""
Comprehensive setup script for the Workflow Automation Engine.
This script sets up all components needed to run the system.
"""

import os
import sys
import subprocess
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WorkflowEngineSetup:
    """Main setup class for the Workflow Automation Engine."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.absolute()
        self.venv_path = self.project_root / "venv"
        self.env_file = self.project_root / ".env"
        self.setup_log = []
        
    def log_step(self, step: str, success: bool, message: str = ""):
        """Log a setup step."""
        status = "✅" if success else "❌"
        log_entry = f"{status} {step}"
        if message:
            log_entry += f": {message}"
        
        logger.info(log_entry)
        self.setup_log.append(log_entry)
        
    def run_command(self, command: str, description: str, cwd: Optional[Path] = None) -> Tuple[bool, str]:
        """Run a command and return success status and output."""
        try:
            logger.info(f"🔧 {description}")
            logger.debug(f"Running: {command}")
            
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                capture_output=True,
                text=True,
                cwd=cwd or self.project_root
            )
            
            output = result.stdout.strip()
            if output:
                logger.debug(f"Output: {output}")
                
            return True, output
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.error(f"Command failed: {error_msg}")
            return False, error_msg
    
    def check_python_version(self) -> bool:
        """Check if Python version is compatible."""
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 9):
            self.log_step("Python version check", False, f"Python 3.9+ required, found {version.major}.{version.minor}")
            return False
        
        self.log_step("Python version check", True, f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    
    def create_virtual_environment(self) -> bool:
        """Create Python virtual environment."""
        if self.venv_path.exists():
            self.log_step("Virtual environment", True, "Already exists")
            return True
            
        success, output = self.run_command(
            f"python -m venv {self.venv_path}",
            "Creating virtual environment"
        )
        
        if success:
            self.log_step("Virtual environment", True, "Created successfully")
        else:
            self.log_step("Virtual environment", False, output)
            
        return success
    
    def get_pip_command(self) -> str:
        """Get the pip command for the virtual environment."""
        if os.name == 'nt':  # Windows
            return str(self.venv_path / "Scripts" / "pip")
        else:  # Unix-like
            return str(self.venv_path / "bin" / "pip")
    
    def get_python_command(self) -> str:
        """Get the python command for the virtual environment."""
        if os.name == 'nt':  # Windows
            return str(self.venv_path / "Scripts" / "python")
        else:  # Unix-like
            return str(self.venv_path / "bin" / "python")
    
    def install_dependencies(self) -> bool:
        """Install Python dependencies."""
        pip_cmd = self.get_pip_command()
        
        # Upgrade pip first
        success, _ = self.run_command(
            f"{pip_cmd} install --upgrade pip",
            "Upgrading pip"
        )
        
        if not success:
            self.log_step("Dependencies", False, "Failed to upgrade pip")
            return False
        
        # Install main requirements
        success, output = self.run_command(
            f"{pip_cmd} install -r requirements.txt",
            "Installing main dependencies"
        )
        
        if not success:
            self.log_step("Dependencies", False, output)
            return False
        
        # Install service-specific requirements (if any exist)
        service_requirements = [
            "services/dsl_generator/requirements.txt"
        ]
        
        for req_file in service_requirements:
            req_path = self.project_root / req_file
            if req_path.exists():
                success, output = self.run_command(
                    f"{pip_cmd} install -r {req_path}",
                    f"Installing {req_file}"
                )
                if not success:
                    logger.warning(f"Failed to install {req_file}: {output}")
        
        self.log_step("Dependencies", True, "Installed successfully")
        return True
    
    def create_env_file(self) -> bool:
        """Create .env file with default configuration."""
        if self.env_file.exists():
            logger.info("⚠️  .env file already exists")
            response = input("Do you want to overwrite it? (y/N): ").strip().lower()
            if response != 'y':
                self.log_step("Environment file", True, "Using existing file")
                return True
        
        env_content = """# Workflow Automation Engine Environment Variables
# Generated by setup.py

# Database Configuration
DATABASE_URL=mongodb+srv://dylan:43VFMVJVJUFAII9g@cluster0.8phbhhb.mongodb.net/weave-dev-db?retryWrites=true&w=majority

# Redis Configuration
REDIS_URL=redis://localhost:6379

# API Keys (REQUIRED - Update these with your actual keys)
COMPOSIO_API_KEY=your_composio_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GROQ_API_KEY=your_groq_api_key_here

# Composio Configuration
COMPOSIO_BASE_URL=https://api.composio.dev

# Application Settings
DEBUG=false
LOG_LEVEL=INFO

# Service URLs
SCHEDULER_URL=http://localhost:8003
WEAVE_API_BASE=http://localhost:8001

# API Server Configuration
API_HOST=0.0.0.0
API_PORT=8001
"""
        
        try:
            with open(self.env_file, 'w') as f:
                f.write(env_content)
            
            self.log_step("Environment file", True, "Created successfully")
            return True
            
        except Exception as e:
            self.log_step("Environment file", False, str(e))
            return False
    
    def check_external_services(self) -> bool:
        """Check if external services are available."""
        services_ok = True
        
        # Check Redis
        success, _ = self.run_command("redis-cli ping", "Checking Redis connection")
        if success:
            self.log_step("Redis", True, "Running and accessible")
        else:
            self.log_step("Redis", False, "Not running or not accessible")
            services_ok = False
        
        # Check MongoDB (basic connectivity test)
        try:
            import pymongo
            from urllib.parse import urlparse
            
            # Parse DATABASE_URL to test connection
            database_url = os.getenv("DATABASE_URL", "mongodb+srv://dylan:43VFMVJVJUFAII9g@cluster0.8phbhhb.mongodb.net/weave-dev-db?retryWrites=true&w=majority")
            
            # Test connection (this will fail if MongoDB is not accessible)
            client = pymongo.MongoClient(database_url, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            client.close()
            
            self.log_step("MongoDB", True, "Accessible")
            
        except Exception as e:
            self.log_step("MongoDB", False, f"Connection failed: {str(e)}")
            services_ok = False
        
        return services_ok
    
    async def setup_database(self) -> bool:
        """Set up database collections and indexes."""
        try:
            python_cmd = self.get_python_command()
            
            # Run MongoDB migration
            success, output = self.run_command(
                f"{python_cmd} scripts/migrate_to_mongodb.py",
                "Setting up MongoDB collections and indexes"
            )
            
            if success:
                self.log_step("Database setup", True, "Collections and indexes created")
                return True
            else:
                self.log_step("Database setup", False, output)
                return False
                
        except Exception as e:
            self.log_step("Database setup", False, str(e))
            return False
    
    async def setup_catalog(self) -> bool:
        """Set up the catalog system."""
        try:
            python_cmd = self.get_python_command()
            
            # Test catalog setup
            success, output = self.run_command(
                f"{python_cmd} scripts/catalog/test_catalog_setup.py",
                "Testing catalog system setup"
            )
            
            if success:
                self.log_step("Catalog system", True, "Setup verified")
                return True
            else:
                self.log_step("Catalog system", False, output)
                return False
                
        except Exception as e:
            self.log_step("Catalog system", False, str(e))
            return False
    
    def create_startup_scripts(self) -> bool:
        """Create convenient startup scripts."""
        # No additional startup scripts needed - just use python api/run.py
        self.log_step("Startup scripts", True, "No additional scripts needed")
        return True
    
    def print_setup_summary(self):
        """Print setup summary and next steps."""
        print("\n" + "="*60)
        print("🎉 WORKFLOW AUTOMATION ENGINE SETUP COMPLETE")
        print("="*60)
        
        print("\n📋 Setup Summary:")
        for log_entry in self.setup_log:
            print(f"   {log_entry}")
        
        print("\n🔧 Next Steps:")
        print("1. Update API keys in .env file:")
        print("   - COMPOSIO_API_KEY (required for catalog)")
        print("   - ANTHROPIC_API_KEY (required for AI suggestions)")
        print("   - GROQ_API_KEY (optional, for fast tool retrieval)")
        
        print("\n2. Ensure external services are running:")
        print("   - Redis: brew services start redis (macOS)")
        print("   - MongoDB: Already configured (cloud instance)")
        
        print("\n3. Start the application:")
        print("   - API Server: python api/run.py")
        
        print("\n4. Access the application:")
        print("   - Backend API: http://localhost:8001")
        print("   - API Documentation: http://localhost:8001/docs")
        
        print("\n5. Test the setup:")
        print("   - python scripts/catalog/test_catalog_setup.py")
        print("   - curl http://localhost:8001/health")
        
        print("\n📚 Documentation:")
        print("   - README.md - Main documentation")
        print("   - QUICK_START.md - Quick start guide")
        print("   - docs/ - Detailed documentation")
        
        print("\n🚀 Happy automating!")
    
    async def run_setup(self):
        """Run the complete setup process."""
        print("🚀 Workflow Automation Engine Setup")
        print("="*50)
        
        # Core setup steps
        setup_steps = [
            ("Python version check", self.check_python_version),
            ("Virtual environment", self.create_virtual_environment),
            ("Dependencies", self.install_dependencies),
            ("Environment file", self.create_env_file),
            ("External services", self.check_external_services),
            ("Database setup", self.setup_database),
            ("Catalog system", self.setup_catalog),
            ("Startup scripts", self.create_startup_scripts),
        ]
        
        # Run setup steps
        for step_name, step_func in setup_steps:
            print(f"\n{'='*20} {step_name.upper()} {'='*20}")
            
            try:
                if asyncio.iscoroutinefunction(step_func):
                    success = await step_func()
                else:
                    success = step_func()
                
                if not success:
                    print(f"\n❌ Setup failed at: {step_name}")
                    print("Please fix the issues above and run the script again.")
                    return False
                    
            except Exception as e:
                logger.error(f"Unexpected error in {step_name}: {e}")
                self.log_step(step_name, False, str(e))
                return False
        
        # Print summary
        self.print_setup_summary()
        return True

async def main():
    """Main entry point."""
    setup = WorkflowEngineSetup()
    success = await setup.run_setup()
    
    if success:
        print("\n✅ Setup completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Setup failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
