"""
Database configuration for the workflow engine catalog
"""

import os
from typing import Dict, Any

def get_database_config() -> Dict[str, Any]:
    """Get database configuration from environment variables or defaults"""
    
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'workflow_engine'),
        'user': os.getenv('DB_USER', 'talishawhite'),  # Your system username
        'password': os.getenv('DB_PASSWORD', ''),  # No password for local setup
        'port': int(os.getenv('DB_PORT', '5432')),
        'sslmode': os.getenv('DB_SSLMODE', 'prefer')
    }

def get_database_url() -> str:
    """Get database URL for SQLAlchemy"""
    
    config = get_database_config()
    
    if config['password']:
        return f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
    else:
        return f"postgresql://{config['user']}@{config['host']}:{config['port']}/{config['database']}"

# Database schema information
CATALOG_TABLES = [
    'toolkit_categories',
    'toolkits', 
    'toolkit_auth_schemes',
    'tools',
    'tool_parameters',
    'tool_parameters',
    'tool_returns',
    'tool_examples',
    'toolkit_rate_limits',
    'catalog_snapshots'
]

# User tables
USER_TABLES = [
    'users',
    'user_preferences'
]

# All tables
ALL_TABLES = CATALOG_TABLES + USER_TABLES

# Default categories that should exist
DEFAULT_CATEGORIES = [
    ('collaboration', 'Collaboration & Communication', 'Team communication and collaboration tools', 1),
    ('productivity', 'Productivity & Project Management', 'Tools for managing projects and increasing productivity', 2),
    ('crm', 'Customer Relationship Management', 'Tools for managing customer relationships and sales', 3),
    ('marketing', 'Marketing & Social Media', 'Marketing automation and social media management', 4),
    ('developer', 'Developer Tools & DevOps', 'Development, deployment, and operations tools', 5),
    ('finance', 'Finance & Accounting', 'Financial management and accounting tools', 6),
    ('ecommerce', 'E-commerce & Retail', 'Online selling and retail management tools', 7),
    ('analytics', 'Analytics & Data', 'Data analysis and business intelligence tools', 8),
    ('design', 'Design & Creative', 'Design, creative, and multimedia tools', 9),
    ('other', 'Other & Miscellaneous', 'Other tools and integrations', 10)
]
