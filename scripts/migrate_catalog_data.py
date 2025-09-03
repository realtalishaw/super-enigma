#!/usr/bin/env python3
"""
Data migration script to transfer catalog data from PostgreSQL to MongoDB.
This script will migrate all your existing catalog data including toolkits, tools, and categories.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
import json

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# PostgreSQL imports
import psycopg2
from psycopg2.extras import RealDictCursor

# MongoDB imports
from motor.motor_asyncio import AsyncIOMotorClient
from database.config import get_database_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CatalogDataMigrator:
    """Migrate catalog data from PostgreSQL to MongoDB"""
    
    def __init__(self, postgres_url: str, mongodb_url: str):
        self.postgres_url = postgres_url
        self.mongodb_url = mongodb_url
        self.pg_conn = None
        self.mongo_client = None
        self.mongo_db = None
    
    async def connect_mongodb(self):
        """Connect to MongoDB"""
        try:
            self.mongo_client = AsyncIOMotorClient(self.mongodb_url)
            self.mongo_db = self.mongo_client.get_database()
            
            # Test connection
            await self.mongo_client.admin.command('ping')
            logger.info("✅ Connected to MongoDB successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise
    
    def connect_postgresql(self):
        """Connect to PostgreSQL"""
        try:
            self.pg_conn = psycopg2.connect(self.postgres_url)
            logger.info("✅ Connected to PostgreSQL successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
            raise
    
    async def migrate_categories(self):
        """Migrate toolkit categories"""
        logger.info("🔄 Migrating toolkit categories...")
        
        try:
            with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT name, display_name, description, sort_order, created_at
                    FROM toolkit_categories
                    ORDER BY sort_order
                """)
                categories = cursor.fetchall()
            
            migrated_count = 0
            for category in categories:
                try:
                    # Convert to MongoDB document format
                    category_doc = {
                        "name": category["name"],
                        "display_name": category["display_name"],
                        "description": category["description"],
                        "sort_order": category["sort_order"],
                        "created_at": category["created_at"],
                        "updated_at": category["created_at"]  # Use created_at as updated_at if updated_at doesn't exist
                    }
                    
                    # Upsert to avoid duplicates
                    await self.mongo_db.toolkit_categories.update_one(
                        {"name": category["name"]},
                        {"$set": category_doc},
                        upsert=True
                    )
                    migrated_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to migrate category {category['name']}: {e}")
            
            logger.info(f"✅ Migrated {migrated_count} categories")
            
        except Exception as e:
            logger.error(f"❌ Failed to migrate categories: {e}")
            raise
    
    async def migrate_toolkits(self):
        """Migrate toolkits/providers"""
        logger.info("🔄 Migrating toolkits...")
        
        try:
            with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        toolkit_id, slug, name, description, logo_url, website_url, 
                        category, version, created_at, last_synced_at,
                        is_deprecated
                    FROM toolkits
                    ORDER BY name
                """)
                toolkits = cursor.fetchall()
            
            migrated_count = 0
            for toolkit in toolkits:
                try:
                    # Convert to MongoDB document format
                    toolkit_doc = {
                        "slug": toolkit["slug"],
                        "name": toolkit["name"],
                        "description": toolkit["description"],
                        "logo_url": toolkit["logo_url"],
                        "website_url": toolkit["website_url"],
                        "category": toolkit["category"],
                        "version": toolkit["version"],
                        "created_at": toolkit["created_at"],
                        "updated_at": toolkit["created_at"],  # Use created_at as updated_at if updated_at doesn't exist
                        "last_synced_at": toolkit["last_synced_at"],
                        "is_deprecated": toolkit["is_deprecated"] or False
                    }
                    
                    # Upsert to avoid duplicates
                    await self.mongo_db.toolkits.update_one(
                        {"slug": toolkit["slug"]},
                        {"$set": toolkit_doc},
                        upsert=True
                    )
                    migrated_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to migrate toolkit {toolkit['slug']}: {e}")
            
            logger.info(f"✅ Migrated {migrated_count} toolkits")
            
        except Exception as e:
            logger.error(f"❌ Failed to migrate toolkits: {e}")
            raise
    
    async def migrate_tools(self):
        """Migrate tools"""
        logger.info("🔄 Migrating tools...")
        
        try:
            with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        t.tool_id, t.slug, t.name, t.display_name, t.description,
                        t.tool_type, t.version, t.input_schema, t.output_schema,
                        t.tags, t.created_at, t.is_deprecated,
                        tk.slug as toolkit_slug
                    FROM tools t
                    JOIN toolkits tk ON t.toolkit_id = tk.toolkit_id
                    ORDER BY tk.slug, t.name
                """)
                tools = cursor.fetchall()
            
            migrated_count = 0
            for tool in tools:
                try:
                    # Get toolkit ID from MongoDB
                    toolkit_doc = await self.mongo_db.toolkits.find_one({"slug": tool["toolkit_slug"]})
                    if not toolkit_doc:
                        logger.warning(f"Toolkit {tool['toolkit_slug']} not found, skipping tool {tool['slug']}")
                        continue
                    
                    # Convert to MongoDB document format
                    tool_doc = {
                        "slug": tool["slug"],
                        "name": tool["name"],
                        "display_name": tool["display_name"],
                        "description": tool["description"],
                        "tool_type": tool["tool_type"],
                        "version": tool["version"],
                        "input_schema": tool["input_schema"] if tool["input_schema"] else {},
                        "output_schema": tool["output_schema"] if tool["output_schema"] else {},
                        "tags": tool["tags"] if tool["tags"] else [],
                        "created_at": tool["created_at"],
                        "updated_at": tool["created_at"],  # Use created_at as updated_at if updated_at doesn't exist
                        "is_deprecated": tool["is_deprecated"] or False,
                        "toolkit_id": str(toolkit_doc["_id"])
                    }
                    
                    # Upsert to avoid duplicates
                    await self.mongo_db.tools.update_one(
                        {"slug": tool["slug"], "toolkit_id": str(toolkit_doc["_id"])},
                        {"$set": tool_doc},
                        upsert=True
                    )
                    migrated_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to migrate tool {tool['slug']}: {e}")
            
            logger.info(f"✅ Migrated {migrated_count} tools")
            
        except Exception as e:
            logger.error(f"❌ Failed to migrate tools: {e}")
            raise
    
    async def migrate_tool_parameters(self):
        """Migrate tool parameters"""
        logger.info("🔄 Migrating tool parameters...")
        
        try:
            with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        p.name, p.display_name, p.description,
                        p.param_type, p.is_required, p.default_value, p.validation_rules,
                        p.sort_order, p.created_at,
                        t.slug as tool_slug, tk.slug as toolkit_slug
                    FROM tool_parameters p
                    JOIN tools t ON p.tool_id = t.tool_id
                    JOIN toolkits tk ON t.toolkit_id = tk.toolkit_id
                    ORDER BY tk.slug, t.slug, p.sort_order
                """)
                parameters = cursor.fetchall()
            
            migrated_count = 0
            for param in parameters:
                try:
                    # Get tool ID from MongoDB
                    tool_doc = await self.mongo_db.tools.find_one({
                        "slug": param["tool_slug"],
                        "toolkit_id": {"$in": [await self.mongo_db.toolkits.find_one({"slug": param["toolkit_slug"]})["_id"]]}
                    })
                    
                    if not tool_doc:
                        logger.warning(f"Tool {param['tool_slug']} not found, skipping parameter {param['name']}")
                        continue
                    
                    # Convert to MongoDB document format
                    param_doc = {
                        "name": param["name"],
                        "display_name": param["display_name"],
                        "description": param["description"],
                        "param_type": param["param_type"],
                        "is_required": param["is_required"],
                        "default_value": param["default_value"],
                        "validation_rules": param["validation_rules"] if param["validation_rules"] else {},
                        "sort_order": param["sort_order"],
                        "created_at": param["created_at"],
                        "updated_at": param["created_at"],  # Use created_at as updated_at if updated_at doesn't exist
                        "tool_id": str(tool_doc["_id"])
                    }
                    
                    # Upsert to avoid duplicates
                    await self.mongo_db.tool_parameters.update_one(
                        {"name": param["name"], "tool_id": str(tool_doc["_id"])},
                        {"$set": param_doc},
                        upsert=True
                    )
                    migrated_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to migrate parameter {param['name']}: {e}")
            
            logger.info(f"✅ Migrated {migrated_count} tool parameters")
            
        except Exception as e:
            logger.error(f"❌ Failed to migrate tool parameters: {e}")
            raise
    
    async def migrate_users_and_preferences(self):
        """Migrate users and user preferences"""
        logger.info("🔄 Migrating users and preferences...")
        
        try:
            # Migrate users
            with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT user_id, email, created_at
                    FROM users
                """)
                users = cursor.fetchall()
            
            user_migrated = 0
            for user in users:
                try:
                    user_doc = {
                        "email": user["email"],
                        "created_at": user["created_at"],
                        "updated_at": user["created_at"]  # Use created_at as updated_at if updated_at doesn't exist
                    }
                    
                    await self.mongo_db.users.update_one(
                        {"email": user["email"]},
                        {"$set": user_doc},
                        upsert=True
                    )
                    user_migrated += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to migrate user {user['email']}: {e}")
            
            logger.info(f"✅ Migrated {user_migrated} users")
            
            # Migrate user preferences
            with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT user_id, preference_key, preference_value, created_at
                    FROM user_preferences
                """)
                preferences = cursor.fetchall()
            
            pref_migrated = 0
            for pref in preferences:
                try:
                    # Get user from MongoDB (user_id in PG is email in Mongo)
                    user_doc = await self.mongo_db.users.find_one({"email": pref["user_id"]})
                    if not user_doc:
                        logger.warning(f"User {pref['user_id']} not found, skipping preference {pref['preference_key']}")
                        continue
                    
                    pref_doc = {
                        "user_id": str(user_doc["_id"]),
                        "preference_key": pref["preference_key"],
                        "preference_value": pref["preference_value"],
                        "created_at": pref["created_at"],
                        "updated_at": pref["created_at"]  # Use created_at as updated_at if updated_at doesn't exist
                    }
                    
                    await self.mongo_db.user_preferences.update_one(
                        {"user_id": str(user_doc["_id"]), "preference_key": pref["preference_key"]},
                        {"$set": pref_doc},
                        upsert=True
                    )
                    pref_migrated += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to migrate preference {pref['preference_key']}: {e}")
            
            logger.info(f"✅ Migrated {pref_migrated} user preferences")
            
        except Exception as e:
            logger.error(f"❌ Failed to migrate users and preferences: {e}")
            raise
    
    async def run_migration(self, start_from_step=None):
        """Run the complete migration"""
        logger.info("🚀 Starting PostgreSQL to MongoDB catalog data migration...")
        
        try:
            # Connect to both databases
            self.connect_postgresql()
            await self.connect_mongodb()
            
            # Define migration steps
            migration_steps = [
                ("categories", self.migrate_categories),
                ("toolkits", self.migrate_toolkits),
                ("tools", self.migrate_tools),
                ("tool_parameters", self.migrate_tool_parameters),
                ("users_and_preferences", self.migrate_users_and_preferences)
            ]
            
            # Find starting point
            start_index = 0
            if start_from_step:
                for i, (step_name, _) in enumerate(migration_steps):
                    if step_name == start_from_step:
                        start_index = i
                        logger.info(f"🔄 Resuming migration from step: {start_from_step}")
                        break
                else:
                    logger.warning(f"⚠️  Unknown step '{start_from_step}', starting from beginning")
            
            # Run migrations from the starting point
            for i in range(start_index, len(migration_steps)):
                step_name, step_func = migration_steps[i]
                logger.info(f"🔄 Running step {i+1}/{len(migration_steps)}: {step_name}")
                await step_func()
            
            # Get final statistics
            toolkit_count = await self.mongo_db.toolkits.count_documents({})
            tool_count = await self.mongo_db.tools.count_documents({})
            category_count = await self.mongo_db.toolkit_categories.count_documents({})
            user_count = await self.mongo_db.users.count_documents({})
            pref_count = await self.mongo_db.user_preferences.count_documents({})
            
            logger.info(f"\n🎉 Migration completed successfully!")
            logger.info(f"\n📊 Final MongoDB Statistics:")
            logger.info(f"   Toolkits: {toolkit_count}")
            logger.info(f"   Tools: {tool_count}")
            logger.info(f"   Categories: {category_count}")
            logger.info(f"   Users: {user_count}")
            logger.info(f"   User Preferences: {pref_count}")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise
        finally:
            # Clean up connections
            if self.pg_conn:
                self.pg_conn.close()
            if self.mongo_client:
                self.mongo_client.close()

async def main(postgres_url: str, start_from_step: str = None):
    """Main migration function"""
    # MongoDB URL from your config
    mongodb_url = get_database_url()
    
    migrator = CatalogDataMigrator(postgres_url, mongodb_url)
    await migrator.run_migration(start_from_step)

if __name__ == "__main__":
    # Check if PostgreSQL URL is provided
    if len(sys.argv) > 1:
        postgres_url = sys.argv[1]
        start_from_step = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        print("❌ Please provide your PostgreSQL connection string as an argument")
        print("Usage: python scripts/migrate_catalog_data.py 'postgresql://user:pass@host:port/db' [start_from_step]")
        print("\nExamples:")
        print("python scripts/migrate_catalog_data.py 'postgresql://talishawhite@localhost:5432/workflow_engine'")
        print("python scripts/migrate_catalog_data.py 'postgresql://talishawhite@localhost:5432/workflow_engine' tool_parameters")
        print("\nAvailable steps: categories, toolkits, tools, tool_parameters, users_and_preferences")
        sys.exit(1)
    
    # Run migration
    asyncio.run(main(postgres_url, start_from_step))
