"""
Frontend user preferences routes.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from uuid import UUID
import logging

from api.user_services.user_service import UserService

router = APIRouter(prefix="/preferences", tags=["Preferences"])

# Initialize user service
user_service = UserService()

async def get_user_service() -> UserService:
    """Dependency to get user service instance"""
    return user_service

@router.get("/{user_id}")
async def get_user_preferences(
    user_id: UUID,
    user_service: UserService = Depends(get_user_service)
):
    """Get all preferences for a specific user"""
    try:
        preferences = await user_service.get_user_preferences(user_id)
        return {
            "user_id": str(user_id),
            "preferences": preferences,
            "count": len(preferences)
        }
    except Exception as e:
        logging.error(f"Failed to fetch preferences for user {user_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch user preferences: {str(e)}"
        )
