#!/usr/bin/env python3
"""
Setup script to create .env file for the workflow automation engine.

This script will create a .env file in the project root with the required configuration.
"""

import os
from pathlib import Path

def create_env_file():
    """Create .env file with required configuration"""
    
    # Get the project root directory
    project_root = Path(__file__).parent
    
    # .env file path
    env_file_path = project_root / ".env"
    
    # Check if .env already exists
    if env_file_path.exists():
        print("⚠️  .env file already exists!")
        response = input("Do you want to overwrite it? (y/N): ")
        if response.lower() != 'y':
            print("Aborting...")
            return
    
    # .env content template
    env_content = """# API Keys
# Get your Groq API key from: https://console.groq.com/
GROQ_API_KEY=your_groq_api_key_here

# Get your Anthropic API key from: https://console.anthropic.com/
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/workflow_engine

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Application Settings
ENVIRONMENT=development
LOG_LEVEL=INFO
DEBUG=false

# Service URLs
SCHEDULER_URL=http://localhost:8003
COMPOSIO_BASE_URL=https://api.composio.dev
COMPOSIO_API_KEY=your_composio_api_key_here

# RAG Workflow Tool Limits (to prevent Claude API size limits)
MAX_TRIGGERS=10
MAX_ACTIONS=20
MAX_PROVIDERS=8
"""
    
    try:
        # Write .env file
        with open(env_file_path, 'w') as f:
            f.write(env_content)
        
        print(f"✅ .env file created successfully at: {env_file_path}")
        print("\n📝 Next steps:")
        print("1. Edit the .env file and replace the placeholder values with your actual API keys")
        print("2. Set GROQ_API_KEY to enable intelligent tool search")
        print("3. Set ANTHROPIC_API_KEY for Claude workflow generation")
        print("4. Update other configuration values as needed")
        print("\n⚠️  Important: Never commit your .env file to version control!")
        
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")

if __name__ == "__main__":
    create_env_file()
