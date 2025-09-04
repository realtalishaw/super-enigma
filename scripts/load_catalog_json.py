#!/usr/bin/env python3
"""
Script to load catalog data from JSON file into MongoDB.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from motor.motor_asyncio import AsyncIOMotorClient
from database.config import get_database_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def load_catalog_from_json(json_file_path: str):
    """Load catalog data from JSON file into MongoDB."""
    try:
        # Connect to MongoDB
        database_url = get_database_url()
        logger.info(f"Connecting to MongoDB...")
        
        client = AsyncIOMotorClient(database_url)
        database = client.get_database()
        
        # Test connection
        await client.admin.command('ping')
        logger.info("✅ Successfully connected to MongoDB")
        
        # Load JSON data
        logger.info(f"Loading catalog data from {json_file_path}...")
        with open(json_file_path, 'r') as f:
            catalog_data = json.load(f)
        
        # Extract data
        catalog = catalog_data.get('catalog', {})
        toolkits_data = catalog.get('providers', {})
        summary = catalog.get('summary', {})
        
        logger.info(f"Found {len(toolkits_data)} toolkits in JSON file")
        logger.info(f"Summary: {summary}")
        
        # Clear existing data
        logger.info("Clearing existing catalog data...")
        await database.toolkits.delete_many({})
        await database.tools.delete_many({})
        await database.toolkit_categories.delete_many({})
        
        # Load toolkits
        toolkit_count = 0
        tool_count = 0
        
        for toolkit_slug, toolkit_info in toolkits_data.items():
            # Insert toolkit
            toolkit_doc = {
                'slug': toolkit_slug,
                'name': toolkit_info.get('name', toolkit_slug),
                'description': toolkit_info.get('description', ''),
                'category': toolkit_info.get('category', ''),
                'website': toolkit_info.get('website', ''),
                'version': toolkit_info.get('version', '1.0.0'),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
                'last_synced_at': datetime.now(timezone.utc),
                'stats': toolkit_info.get('stats', {})
            }
            
            await database.toolkits.insert_one(toolkit_doc)
            toolkit_count += 1
            
            # Insert tools for this toolkit
            stats = toolkit_info.get('stats', {})
            total_tools = stats.get('total_tools', 0)
            
            if total_tools > 0:
                # Create placeholder tools
                for i in range(total_tools):
                    tool_doc = {
                        'toolkit_id': toolkit_slug,
                        'name': f"{toolkit_slug}_tool_{i+1}",
                        'slug': f"{toolkit_slug}_tool_{i+1}",
                        'description': f"Tool {i+1} for {toolkit_slug}",
                        'tool_type': 'action',
                        'is_deprecated': False,
                        'created_at': datetime.now(timezone.utc),
                        'updated_at': datetime.now(timezone.utc)
                    }
                    await database.tools.insert_one(tool_doc)
                    tool_count += 1
        
        # Create default categories
        default_categories = [
            'productivity', 'communication', 'marketing', 'development', 'analytics',
            'finance', 'crm', 'automation', 'ai', 'data'
        ]
        
        for category in default_categories:
            category_doc = {
                'name': category,
                'slug': category,
                'description': f"{category.title()} tools and integrations",
                'sort_order': default_categories.index(category),
                'created_at': datetime.now(timezone.utc)
            }
            await database.toolkit_categories.insert_one(category_doc)
        
        logger.info(f"\n📊 Catalog loaded successfully!")
        logger.info(f"   Toolkits: {toolkit_count}")
        logger.info(f"   Tools: {tool_count}")
        logger.info(f"   Categories: {len(default_categories)}")
        
        client.close()
        
    except Exception as e:
        logger.error(f"❌ Failed to load catalog: {e}")
        raise

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/load_catalog_json.py <json_file_path>")
        print("Example: python scripts/load_catalog_json.py catalog_clean.json")
        sys.exit(1)
    
    json_file = sys.argv[1]
    asyncio.run(load_catalog_from_json(json_file))
