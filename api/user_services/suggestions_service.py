"""
Suggestions database service for storing and retrieving workflow suggestions.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bson import ObjectId

logger = logging.getLogger(__name__)

class SuggestionsService:
    """Service for managing user suggestions and workflow recommendations"""
    
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
            # Indexes for suggestions collection
            await self.database.suggestions.create_index([("suggestion_id", 1)], unique=True)
            await self.database.suggestions.create_index([("user_id", 1)])
            await self.database.suggestions.create_index([("created_at", -1)])
            
            logger.info("MongoDB indexes created successfully for suggestions service")
        except Exception as e:
            logger.warning(f"Failed to create some indexes for suggestions service: {e}")
    
    async def save_suggestion(
        self,
        user_id: str,
        user_request: str,
        selected_apps: List[str],
        suggestion_id: str,
        title: str,
        description: str,
        dsl_parametric: Dict[str, Any],
        missing_fields: List[Dict[str, Any]],
        confidence: float,
        apps: List[str],
        source: str,
        full_workflow_json: Optional[Dict[str, Any]] = None,
        generation_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Save a generated suggestion to the database."""
        try:
            await self._ensure_client()
            
            now = datetime.now(timezone.utc)
            suggestion_data = {
                "user_id": user_id,
                "user_request": user_request,
                "selected_apps": selected_apps,
                "suggestion_id": suggestion_id,
                "title": title,
                "description": description,
                "dsl_parametric": dsl_parametric,
                "missing_fields": missing_fields,
                "confidence_score": confidence,
                "apps": apps,
                "source": source,
                "full_workflow_json": full_workflow_json,
                "generation_metadata": generation_metadata,
                "created_at": now,
                "updated_at": now
            }
            
            await self.database.suggestions.insert_one(suggestion_data)
            
            logger.info(f"Saved suggestion {suggestion_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save suggestion {suggestion_id}: {e}")
            return False
    
    async def get_suggestion(self, suggestion_id: str) -> Optional[Dict[str, Any]]:
        """Get a suggestion by ID."""
        try:
            await self._ensure_client()
            
            suggestion_doc = await self.database.suggestions.find_one({"suggestion_id": suggestion_id})
            
            if suggestion_doc:
                # Convert ObjectId to string
                suggestion_doc["_id"] = str(suggestion_doc["_id"])
                return suggestion_doc
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get suggestion {suggestion_id}: {e}")
            return None
    
    async def get_user_suggestions(
        self, 
        user_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get suggestions for a specific user."""
        try:
            await self._ensure_client()
            
            cursor = self.database.suggestions.find({"user_id": user_id}).sort("created_at", -1).skip(offset).limit(limit)
            
            suggestions = []
            async for suggestion_doc in cursor:
                # Convert ObjectId to string
                suggestion_doc["_id"] = str(suggestion_doc["_id"])
                suggestions.append(suggestion_doc)
            
            return suggestions
                
        except Exception as e:
            logger.error(f"Failed to get suggestions for user {user_id}: {e}")
            return []
    
    async def update_user_actions(
        self, 
        suggestion_id: str, 
        user_actions: Dict[str, Any]
    ) -> bool:
        """Update user actions for a suggestion (e.g., accepted, rejected, workflow created)."""
        try:
            await self._ensure_client()
            
            update_result = await self.database.suggestions.update_one(
                {"suggestion_id": suggestion_id},
                {"$set": {"user_actions": user_actions, "updated_at": datetime.now(timezone.utc)}}
            )
            
            if update_result.modified_count > 0:
                logger.info(f"Updated user actions for suggestion {suggestion_id}")
                return True
            else:
                logger.warning(f"No suggestion found with ID {suggestion_id} to update user actions.")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update user actions for suggestion {suggestion_id}: {e}")
            return False
    
    async def get_suggestions_analytics(
        self, 
        days: int = 30
    ) -> Dict[str, Any]:
        """Get analytics on suggestions for the last N days."""
        try:
            await self._ensure_client()
            
            # Calculate the date N days ago
            days_ago = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Total suggestions
            total_query = {"created_at": {"$gte": days_ago}}
            total_count = await self.database.suggestions.count_documents(total_query)
            
            # By source
            source_query = {"created_at": {"$gte": days_ago}}
            source_counts = {}
            async for doc in self.database.suggestions.aggregate([
                {"$match": source_query},
                {"$group": {"_id": "$source", "count": {"$sum": 1}}}
            ]):
                source_counts[doc["_id"]] = doc["count"]
                
            # Average confidence
            confidence_query = {"created_at": {"$gte": days_ago}, "confidence_score": {"$ne": None}}
            confidence_result = await self.database.suggestions.aggregate([
                {"$match": confidence_query},
                {"$group": {"_id": None, "avg_confidence": {"$avg": "$confidence_score"}}}
            ])
            avg_confidence = next(confidence_result, {"avg_confidence": 0})["avg_confidence"]
            
            return {
                "total_suggestions": total_count,
                "by_source": source_counts,
                "average_confidence": round(float(avg_confidence), 3),
                "period_days": days
            }
                
        except Exception as e:
            logger.error(f"Failed to get suggestions analytics: {e}")
            return {}
    
    async def close(self):
        """Close database connections."""
        if self.client:
            self.client.close()


async def get_suggestions_service():
    """Get suggestions service instance."""
    from database.config import get_database_url
    database_url = get_database_url()
    return SuggestionsService(database_url)
