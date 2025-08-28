"""
User service for managing users and preferences in the database
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from ..models import User, UserCreate, UserPreferenceCreate
from database.config import get_database_url

logger = logging.getLogger(__name__)

class UserService:
    """Service for managing users and preferences"""
    
    def __init__(self):
        self.database_url = get_database_url()
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
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        await self._ensure_engine()
        
        async with self.session_factory() as session:
            query = text("""
                SELECT user_id, email, created_at, updated_at
                FROM users 
                WHERE email = :email
            """)
            result = await session.execute(query, {"email": email})
            row = result.fetchone()
            
            if row:
                return User(
                    id=row[0],
                    email=row[1],
                    created_at=row[2],
                    updated_at=row[3]
                )
            return None
    
    async def create_user(self, email: str) -> User:
        """Create a new user and return the user object"""
        await self._ensure_engine()
        
        async with self.session_factory() as session:
            query = text("""
                INSERT INTO users (email) 
                VALUES (:email) 
                RETURNING user_id, email, created_at, updated_at
            """)
            result = await session.execute(query, {"email": email})
            row = result.fetchone()
            await session.commit()
            
            return User(
                id=row[0],  # user_id from database
                email=row[1],
                created_at=row[2],
                updated_at=row[3]
            )
    
    async def get_or_create_user(self, email: str) -> User:
        """Get existing user or create new one if doesn't exist"""
        user = await self.get_user_by_email(email)
        if user:
            return user
        
        return await self.create_user(email)
    
    async def get_user_preferences(self, user_id: UUID) -> Dict[str, str]:
        """Get all preferences for a user"""
        await self._ensure_engine()
        
        async with self.session_factory() as session:
            query = text("""
                SELECT preference_key, preference_value
                FROM user_preferences 
                WHERE user_id = :user_id
            """)
            result = await session.execute(query, {"user_id": str(user_id)})
            rows = result.fetchall()
            
            return {row[0]: row[1] for row in rows}
    
    async def set_user_preference(self, user_id: UUID, key: str, value: str) -> bool:
        """Set a user preference (upsert)"""
        await self._ensure_engine()
        
        async with self.session_factory() as session:
            query = text("""
                INSERT INTO user_preferences (user_id, preference_key, preference_value)
                VALUES (:user_id, :key, :value)
                ON CONFLICT (user_id, preference_key) 
                DO UPDATE SET preference_value = :value, updated_at = NOW()
            """)
            await session.execute(query, {
                "user_id": str(user_id),
                "key": key,
                "value": value
            })
            await session.commit()
            return True
    
    async def delete_user_preference(self, user_id: UUID, key: str) -> bool:
        """Delete a user preference"""
        await self._ensure_engine()
        
        async with self.session_factory() as session:
            query = text("""
                DELETE FROM user_preferences 
                WHERE user_id = :user_id AND preference_key = :key
            """)
            result = await session.execute(query, {
                "user_id": str(user_id),
                "key": key
            })
            await session.commit()
            return result.rowcount > 0
