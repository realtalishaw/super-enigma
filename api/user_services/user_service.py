"""
User service for managing users and preferences in the database
"""

import asyncio
import logging
from typing import Dict, Optional
from uuid import UUID
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bson import ObjectId

from api.models import User

logger = logging.getLogger(__name__)

class UserService:
    """Service for managing users and user preferences"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
    
    async def _ensure_client(self):
        """Ensure MongoDB client is initialized"""
        if self.client is None:
            self.client = AsyncIOMotorClient(self.database_url)
            self.database = self.client.get_database()
            
            # Create indexes for better performance
            await self._create_indexes()
    
    async def _create_indexes(self):
        """Create MongoDB indexes for better performance"""
        try:
            # Indexes for users collection
            await self.database.users.create_index([("email", 1)], unique=True)
            
            # Indexes for user_preferences collection
            await self.database.user_preferences.create_index([("user_id", 1), ("preference_key", 1)], unique=True)
            
            logger.info("MongoDB indexes created successfully for user service")
        except Exception as e:
            logger.warning(f"Failed to create some indexes for user service: {e}")
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        await self._ensure_client()
        
        try:
            user_doc = await self.database.users.find_one({"email": email})
            
            if user_doc:
                return User(
                    id=str(user_doc["_id"]),
                    email=user_doc["email"],
                    created_at=user_doc.get("created_at"),
                    updated_at=user_doc.get("updated_at")
                )
            return None
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            return None
    
    async def create_user(self, email: str) -> User:
        """Create a new user and return the user object"""
        await self._ensure_client()
        
        try:
            now = datetime.now(timezone.utc)
            user_data = {
                "email": email,
                "created_at": now,
                "updated_at": now
            }
            
            result = await self.database.users.insert_one(user_data)
            
            return User(
                id=str(result.inserted_id),
                email=email,
                created_at=now,
                updated_at=now
            )
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise
    
    async def get_or_create_user(self, email: str) -> User:
        """Get existing user or create new one if doesn't exist"""
        user = await self.get_user_by_email(email)
        if user:
            return user
        
        return await self.create_user(email)
    
    async def get_user_preferences(self, user_id: UUID) -> Dict[str, str]:
        """Get all preferences for a user"""
        await self._ensure_client()
        
        try:
            cursor = self.database.user_preferences.find({"user_id": str(user_id)})
            preferences = {}
            
            async for doc in cursor:
                preferences[doc["preference_key"]] = doc["preference_value"]
            
            return preferences
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {}
    
    async def set_user_preference(self, user_id: UUID, key: str, value: str) -> bool:
        """Set a user preference (upsert)"""
        await self._ensure_client()
        
        try:
            now = datetime.now(timezone.utc)
            
            result = await self.database.user_preferences.update_one(
                {"user_id": str(user_id), "preference_key": key},
                {
                    "$set": {
                        "preference_value": value,
                        "updated_at": now
                    },
                    "$setOnInsert": {
                        "created_at": now
                    }
                },
                upsert=True
            )
            
            return True
        except Exception as e:
            logger.error(f"Error setting user preference: {e}")
            return False
    
    async def delete_user_preference(self, user_id: UUID, key: str) -> bool:
        """Delete a user preference"""
        await self._ensure_client()
        
        try:
            result = await self.database.user_preferences.delete_one({
                "user_id": str(user_id),
                "preference_key": key
            })
            
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting user preference: {e}")
            return False
