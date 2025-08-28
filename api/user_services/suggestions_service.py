"""
Suggestions database service for storing and retrieving workflow suggestions.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select
import json

from core.config import settings

logger = logging.getLogger(__name__)


class SuggestionsService:
    """Database service for managing workflow suggestions."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.session_factory = None
        
    async def _ensure_engine(self):
        """Ensure database engine is initialized"""
        if self.engine is None:
            # Convert PostgreSQL URL to async version
            async_url = self.database_url.replace('postgresql://', 'postgresql+asyncpg://')
            self.engine = create_async_engine(async_url, echo=False)
            self.session_factory = sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )
    
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
            await self._ensure_engine()
            
            async with self.session_factory() as session:
                query = text("""
                    INSERT INTO suggestions (
                        user_id, user_request, selected_apps, suggestion_id, title, description,
                        dsl_parametric, missing_fields, confidence_score, apps, source,
                        full_workflow_json, generation_metadata
                    ) VALUES (
                        :user_id, :user_request, :selected_apps, :suggestion_id, :title, :description,
                        :dsl_parametric, :missing_fields, :confidence_score, :apps, :source,
                        :full_workflow_json, :generation_metadata
                    )
                """)
                
                await session.execute(query, {
                    "user_id": user_id,
                    "user_request": user_request,
                    "selected_apps": selected_apps,
                    "suggestion_id": suggestion_id,
                    "title": title,
                    "description": description,
                    "dsl_parametric": json.dumps(dsl_parametric),
                    "missing_fields": json.dumps(missing_fields),
                    "confidence_score": confidence,
                    "apps": apps,
                    "source": source,
                    "full_workflow_json": json.dumps(full_workflow_json) if full_workflow_json else None,
                    "generation_metadata": json.dumps(generation_metadata) if generation_metadata else None
                })
                
                await session.commit()
                logger.info(f"Saved suggestion {suggestion_id} for user {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save suggestion {suggestion_id}: {e}")
            return False
    
    async def get_suggestion(self, suggestion_id: str) -> Optional[Dict[str, Any]]:
        """Get a suggestion by ID."""
        try:
            await self._ensure_engine()
            
            async with self.session_factory() as session:
                query = text("""
                    SELECT * FROM suggestions WHERE suggestion_id = :suggestion_id
                """)
                
                result = await session.execute(query, {"suggestion_id": suggestion_id})
                row = result.fetchone()
                
                if row:
                    # Convert row to dict
                    suggestion = dict(row._mapping)
                    # Parse JSON fields - handle both string and dict cases
                    if suggestion.get('dsl_parametric'):
                        if isinstance(suggestion['dsl_parametric'], str):
                            suggestion['dsl_parametric'] = json.loads(suggestion['dsl_parametric'])
                    if suggestion.get('missing_fields'):
                        if isinstance(suggestion['missing_fields'], str):
                            suggestion['missing_fields'] = json.loads(suggestion['missing_fields'])
                    if suggestion.get('full_workflow_json'):
                        if isinstance(suggestion['full_workflow_json'], str):
                            suggestion['full_workflow_json'] = json.loads(suggestion['full_workflow_json'])
                    if suggestion.get('generation_metadata'):
                        if isinstance(suggestion['generation_metadata'], str):
                            suggestion['generation_metadata'] = json.loads(suggestion['generation_metadata'])
                    
                    return suggestion
                
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
            await self._ensure_engine()
            
            async with self.session_factory() as session:
                query = text("""
                    SELECT * FROM suggestions 
                    WHERE user_id = :user_id 
                    ORDER BY created_at DESC 
                    LIMIT :limit OFFSET :offset
                """)
                
                result = await session.execute(query, {
                    "user_id": user_id,
                    "limit": limit,
                    "offset": offset
                })
                
                suggestions = []
                for row in result.fetchall():
                    suggestion = dict(row._mapping)
                    # Parse JSON fields - handle both string and dict cases
                    if suggestion.get('dsl_parametric'):
                        if isinstance(suggestion['dsl_parametric'], str):
                            suggestion['dsl_parametric'] = json.loads(suggestion['dsl_parametric'])
                    if suggestion.get('missing_fields'):
                        if isinstance(suggestion['missing_fields'], str):
                            suggestion['missing_fields'] = json.loads(suggestion['missing_fields'])
                    if suggestion.get('full_workflow_json'):
                        if isinstance(suggestion['full_workflow_json'], str):
                            suggestion['full_workflow_json'] = json.loads(suggestion['full_workflow_json'])
                    if suggestion.get('generation_metadata'):
                        if isinstance(suggestion['generation_metadata'], str):
                            suggestion['generation_metadata'] = json.loads(suggestion['generation_metadata'])
                    
                    suggestions.append(suggestion)
                
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
            await self._ensure_engine()
            
            async with self.session_factory() as session:
                query = text("""
                    UPDATE suggestions 
                    SET user_actions = :user_actions, updated_at = NOW()
                    WHERE suggestion_id = :suggestion_id
                """)
                
                await session.execute(query, {
                    "suggestion_id": suggestion_id,
                    "user_actions": json.dumps(user_actions)
                })
                
                await session.commit()
                logger.info(f"Updated user actions for suggestion {suggestion_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update user actions for suggestion {suggestion_id}: {e}")
            return False
    
    async def get_suggestions_analytics(
        self, 
        days: int = 30
    ) -> Dict[str, Any]:
        """Get analytics on suggestions for the last N days."""
        try:
            await self._ensure_engine()
            
            async with self.session_factory() as session:
                # Total suggestions - use string formatting for INTERVAL since it doesn't support parameters
                total_query = text(f"""
                    SELECT COUNT(*) as total FROM suggestions 
                    WHERE created_at >= NOW() - INTERVAL '{days} days'
                """)
                
                total_result = await session.execute(total_query)
                total = total_result.fetchone()[0]
                
                # By source
                source_query = text(f"""
                    SELECT source, COUNT(*) as count FROM suggestions 
                    WHERE created_at >= NOW() - INTERVAL '{days} days'
                    GROUP BY source
                """)
                
                source_result = await session.execute(source_query)
                source_counts = {row[0]: row[1] for row in source_result.fetchall()}
                
                # Average confidence
                confidence_query = text(f"""
                    SELECT AVG(confidence_score) as avg_confidence FROM suggestions 
                    WHERE created_at >= NOW() - INTERVAL '{days} days' AND confidence_score IS NOT NULL
                """)
                
                confidence_result = await session.execute(confidence_query)
                avg_confidence = confidence_result.fetchone()[0] or 0
                
                return {
                    "total_suggestions": total,
                    "by_source": source_counts,
                    "average_confidence": round(float(avg_confidence), 3),
                    "period_days": days
                }
                
        except Exception as e:
            logger.error(f"Failed to get suggestions analytics: {e}")
            return {}
    
    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()


async def get_suggestions_service():
    """Get suggestions service instance."""
    from database.config import get_database_url
    database_url = get_database_url()
    return SuggestionsService(database_url)
