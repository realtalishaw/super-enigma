#!/usr/bin/env python3
"""
Catalog system setup script.
This script helps you set up the catalog system step by step.
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n🔧 {description}")
    print(f"Running: {command}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        if result.stdout:
            print(f"Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed")
        print(f"Error: {e.stderr}")
        return False

def check_environment():
    """Check if required environment variables are set."""
    print("🔍 Checking environment variables...")
    
    required_vars = {
        "COMPOSIO_API_KEY": "Composio API key for fetching catalog data",
        "DATABASE_URL": "PostgreSQL database connection URL",
        "REDIS_URL": "Redis connection URL"
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✅ {var} is set")
        else:
            print(f"❌ {var} is not set - {description}")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these variables before continuing:")
        for var in missing_vars:
            if var == "COMPOSIO_API_KEY":
                print(f"   export {var}=your_composio_api_key_here")
            elif var == "DATABASE_URL":
                print(f"   export {var}=postgresql://user:password@localhost/workflow_automation")
            elif var == "REDIS_URL":
                print(f"   export {var}=redis://localhost:6379")
        return False
    
    print("✅ All required environment variables are set!")
    return True

def setup_database():
    """Set up the database."""
    print("\n🗄️  Setting up database...")
    
    # Check if PostgreSQL is available
    if not run_command("which psql", "Checking if PostgreSQL is available"):
        print("❌ PostgreSQL not found. Please install PostgreSQL first.")
        return False
    
    # Try to create database
    db_name = "workflow_automation"
    if run_command(f"createdb {db_name}", f"Creating database '{db_name}'"):
        print(f"✅ Database '{db_name}' created successfully")
    else:
        print(f"⚠️  Database '{db_name}' might already exist or creation failed")
    
    # Run schema
    schema_file = "database/schema/catalog_tables.sql"
    if Path(schema_file).exists():
        if run_command(f"psql -d {db_name} -f {schema_file}", "Running catalog schema"):
            print("✅ Database schema applied successfully")
        else:
            print("❌ Failed to apply database schema")
            return False
    else:
        print(f"❌ Schema file not found: {schema_file}")
        return False
    
    return True

def setup_redis():
    """Set up Redis."""
    print("\n🔴 Setting up Redis...")
    
    # Check if Redis is available
    if not run_command("which redis-cli", "Checking if Redis is available"):
        print("❌ Redis not found. Please install Redis first.")
        print("macOS: brew install redis")
        print("Linux: sudo apt-get install redis-server")
        return False
    
    # Test Redis connection
    if run_command("redis-cli ping", "Testing Redis connection"):
        print("✅ Redis is running and accessible")
        return True
    else:
        print("❌ Redis is not running. Please start Redis:")
        print("macOS: brew services start redis")
        print("Linux: sudo systemctl start redis")
        return False

def install_dependencies():
    """Install Python dependencies."""
    print("\n📦 Installing Python dependencies...")
    
    if run_command("pip install -r requirements.txt", "Installing dependencies"):
        print("✅ Dependencies installed successfully")
        return True
    else:
        print("❌ Failed to install dependencies")
        return False

def main():
    """Main setup function."""
    print("🚀 Catalog System Setup")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("core/catalog").exists():
        print("❌ Please run this script from the project root directory")
        sys.exit(1)
    
    steps = [
        ("Environment Check", check_environment),
        ("Install Dependencies", install_dependencies),
        ("Setup Database", setup_database),
        ("Setup Redis", setup_redis),
    ]
    
    print("\n📋 Setup Steps:")
    for i, (name, _) in enumerate(steps, 1):
        print(f"  {i}. {name}")
    
    # Run setup steps
    for name, step_func in steps:
        print(f"\n{'='*20} {name} {'='*20}")
        if not step_func():
            print(f"\n❌ Setup failed at: {name}")
            print("Please fix the issues above and run the script again.")
            sys.exit(1)
    
    print(f"\n{'='*20} Setup Complete {'='*20}")
    print("✅ Catalog system is now set up and ready to use!")
    
    print("\n📚 Next Steps:")
    print("1. Read the documentation: docs/CATALOG_MIGRATION_GUIDE.md")
    print("2. Explore the catalog scripts: scripts/catalog/")
    print("3. Use the catalog in your application")
    print("\nHappy coding! 🚀")

if __name__ == "__main__":
    main()
