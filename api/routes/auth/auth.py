"""
Frontend authentication routes. This is only for testing the suggestion engine.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID

from ...user_services.user_service import UserService
from ...models import User

router = APIRouter(prefix="/auth", tags=["Auth"])



class AuthRequest(BaseModel):
    """Authentication request model"""
    email: EmailStr


class AuthResponse(BaseModel):
    """Authentication response model"""
    user_id: UUID
    email: str
    is_new_user: bool
    message: str




@router.post("/login", response_model=AuthResponse, summary="Login or Create User")
async def login_or_create_user(request: AuthRequest):
    """
    Login with email or create new user if doesn't exist.
    
    This is a simplified authentication for testing purposes.
    Returns user ID and whether this is a new user.
    """
    user_service = UserService()
    
    try:
        # Check if user exists, create if not
        user = await user_service.get_or_create_user(request.email)
        
        # Determine if this is a new user
        is_new_user = user.created_at == user.updated_at
        
        return AuthResponse(
            user_id=user.id,
            email=user.email,
            is_new_user=is_new_user,
            message="User authenticated successfully" if not is_new_user else "New user created successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")



