"""
Database configuration for the workflow engine catalog
"""

import os
from typing import Dict, Any

def get_database_config() -> Dict[str, Any]:
    """Get database configuration from environment variables or defaults"""
    
    return {
        'host': os.getenv('DB_HOST', 'cluster0.8phbhhb.mongodb.net'),
        'database': os.getenv('DB_NAME', 'weave-dev-db'),
        'user': os.getenv('DB_USER', 'dylan'),
        'password': os.getenv('DB_PASSWORD', '43VFMVJVJUFAII9g'),
        'port': int(os.getenv('DB_PORT', '27017')),
        'ssl': os.getenv('DB_SSL', 'true').lower() == 'true',
        'retry_writes': os.getenv('DB_RETRY_WRITES', 'true').lower() == 'true',
        'w': os.getenv('DB_W', 'majority')
    }

def get_database_url() -> str:
    """Get database URL for MongoDB"""
    
    config = get_database_config()
    
    # Build MongoDB connection string
    auth_part = f"{config['user']}:{config['password']}"
    host_part = config['host']
    port_part = f":{config['port']}" if config['port'] != 27017 else ""
    db_part = f"/{config['database']}"
    
    # Build query parameters
    query_params = []
    if config['ssl']:
        query_params.append("ssl=true")
    if config['retry_writes']:
        query_params.append("retryWrites=true")
    if config['w']:
        query_params.append(f"w={config['w']}")
    
    query_string = "&".join(query_params) if query_params else ""
    
    if query_string:
        return f"mongodb+srv://{auth_part}@{host_part}{db_part}?{query_string}"
    else:
        return f"mongodb+srv://{auth_part}@{host_part}{db_part}"

# MongoDB collection names
CATALOG_COLLECTIONS = [
    'toolkit_categories',
    'toolkits', 
    'toolkit_auth_schemes',
    'tools',
    'tool_parameters',
    'tool_returns',
    'tool_examples',
    'toolkit_rate_limits',
    'catalog_snapshots'
]

# User collections
USER_COLLECTIONS = [
    'users',
    'user_preferences'
]

# All collections
ALL_COLLECTIONS = CATALOG_COLLECTIONS + USER_COLLECTIONS

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
