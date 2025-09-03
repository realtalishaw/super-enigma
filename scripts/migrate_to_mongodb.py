#!/usr/bin/env python3
"""
Migration script to help transition from PostgreSQL to MongoDB.
This script creates the necessary MongoDB collections and indexes WITHOUT removing any existing data.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from motor.motor_asyncio import AsyncIOMotorClient
from database.config import get_database_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_to_mongodb():
    """Migrate database structure to MongoDB - SAFE VERSION"""
    try:
        # Connect to MongoDB
        database_url = get_database_url()
        logger.info(f"Connecting to MongoDB: {database_url.split('@')[1]}")  # Hide credentials
        
        client = AsyncIOMotorClient(database_url)
        database = client.get_database()
        
        # Test connection
        await client.admin.command('ping')
        logger.info("✅ Successfully connected to MongoDB")
        
        # Create collections if they don't exist (this won't affect existing collections)
        collections_to_create = [
            'toolkits',
            'tools', 
            'toolkit_categories',
            'toolkit_auth_schemes',
            'tool_parameters',
            'tool_returns',
            'tool_examples',
            'toolkit_rate_limits',
            'catalog_snapshots',
            'users',
            'user_preferences',
            'suggestions'
        ]
        
        existing_collections = await database.list_collection_names()
        logger.info(f"Existing collections: {existing_collections}")
        
        for collection_name in collections_to_create:
            if collection_name not in existing_collections:
                await database.create_collection(collection_name)
                logger.info(f"✅ Created collection: {collection_name}")
            else:
                logger.info(f"ℹ️  Collection already exists: {collection_name} (preserving existing data)")
        
        # Create indexes for better performance - ONLY if they don't already exist
        logger.info("Creating indexes (only if they don't already exist)...")
        
        # Helper function to safely create indexes
        async def safe_create_index(collection, index_spec, unique=False):
            try:
                # Check if index already exists
                existing_indexes = await collection.list_indexes().to_list(length=None)
                index_names = [idx['name'] for idx in existing_indexes]
                
                # Create a simple name for the index
                index_name = "_".join([f"{field}_{direction}" for field, direction in index_spec])
                
                if index_name not in index_names:
                    if unique:
                        await collection.create_index(index_spec, unique=True)
                    else:
                        await collection.create_index(index_spec)
                    logger.info(f"✅ Created index: {index_name}")
                else:
                    logger.info(f"ℹ️  Index already exists: {index_name}")
                    
            except Exception as e:
                logger.warning(f"⚠️  Could not create index {index_spec}: {e}")
        
        # Toolkits collection indexes
        await safe_create_index(database.toolkits, [("slug", 1)], unique=True)
        await safe_create_index(database.toolkits, [("category", 1)])
        await safe_create_index(database.toolkits, [("last_synced_at", 1)])
        await safe_create_index(database.toolkits, [("is_deprecated", 1)])
        
        # Tools collection indexes
        await safe_create_index(database.tools, [("toolkit_id", 1)])
        await safe_create_index(database.tools, [("slug", 1)])
        await safe_create_index(database.tools, [("tool_type", 1)])
        await safe_create_index(database.tools, [("is_deprecated", 1)])
        
        # Categories collection indexes
        await safe_create_index(database.toolkit_categories, [("name", 1)], unique=True)
        await safe_create_index(database.toolkit_categories, [("sort_order", 1)])
        
        # Users collection indexes (only if collection is empty or has valid data)
        try:
            user_count = await database.users.count_documents({})
            if user_count == 0:
                await safe_create_index(database.users, [("email", 1)], unique=True)
            else:
                logger.info("ℹ️  Users collection has existing data - skipping unique email index to avoid conflicts")
        except Exception as e:
            logger.warning(f"⚠️  Could not create users email index: {e}")
        
        # User preferences collection indexes
        await safe_create_index(database.user_preferences, [("user_id", 1), ("preference_key", 1)], unique=True)
        
        # Suggestions collection indexes
        await safe_create_index(database.suggestions, [("suggestion_id", 1)], unique=True)
        await safe_create_index(database.suggestions, [("user_id", 1)])
        await safe_create_index(database.suggestions, [("created_at", -1)])
        
        # Insert default categories if they don't exist (this won't overwrite existing categories)
        default_categories = [
            {"name": "collaboration", "display_name": "Collaboration & Communication", "description": "Team communication and collaboration tools", "sort_order": 1},
            {"name": "productivity", "display_name": "Productivity & Project Management", "description": "Tools for managing projects and increasing productivity", "sort_order": 2},
            {"name": "crm", "display_name": "Customer Relationship Management", "description": "Tools for managing customer relationships and sales", "sort_order": 3},
            {"name": "marketing", "display_name": "Marketing & Social Media", "description": "Marketing automation and social media management", "sort_order": 4},
            {"name": "developer", "display_name": "Developer Tools & DevOps", "description": "Development, deployment, and operations tools", "sort_order": 5},
            {"name": "finance", "display_name": "Finance & Accounting", "description": "Financial management and accounting tools", "sort_order": 6},
            {"name": "ecommerce", "display_name": "E-commerce & Retail", "description": "Online selling and retail management tools", "sort_order": 7},
            {"name": "analytics", "display_name": "Analytics & Data", "description": "Data analysis and business intelligence tools", "sort_order": 8},
            {"name": "design", "display_name": "Design & Creative", "description": "Design, creative, and multimedia tools", "sort_order": 9},
            {"name": "other", "display_name": "Other & Miscellaneous", "description": "Other tools and integrations", "sort_order": 10}
        ]
        
        categories_added = 0
        for category in default_categories:
            try:
                result = await database.toolkit_categories.update_one(
                    {"name": category["name"]},
                    {"$setOnInsert": category},
                    upsert=True
                )
                if result.upserted_id:
                    categories_added += 1
            except Exception as e:
                logger.warning(f"Failed to insert category {category['name']}: {e}")
        
        if categories_added > 0:
            logger.info(f"✅ Added {categories_added} new default categories")
        else:
            logger.info("ℹ️  All default categories already exist")
        
        # Get database stats
        toolkit_count = await database.toolkits.count_documents({})
        tool_count = await database.tools.count_documents({})
        category_count = await database.toolkit_categories.count_documents({})
        user_count = await database.users.count_documents({})
        pref_count = await database.user_preferences.count_documents({})
        
        logger.info(f"\n📊 Database Statistics:")
        logger.info(f"   Toolkits: {toolkit_count}")
        logger.info(f"   Tools: {tool_count}")
        logger.info(f"   Categories: {category_count}")
        logger.info(f"   Users: {user_count}")
        logger.info(f"   User Preferences: {pref_count}")
        
        logger.info("\n🎉 Safe migration to MongoDB completed successfully!")
        logger.info("\n📝 Next steps:")
        logger.info("1. Run the data migration script to transfer your PostgreSQL catalog data")
        logger.info("2. Test your application with the new database")
        logger.info("3. Remove the temporary PostgreSQL dependency when done")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    asyncio.run(migrate_to_mongodb())
