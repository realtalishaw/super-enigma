"""
API models for the workflow automation engine
"""

from pydantic import BaseModel, EmailStr, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from uuid import UUID

# ============================================================================
# Common Models
# ============================================================================

class MissingField(BaseModel):
    path: str
    prompt: str
    type_hint: Optional[str] = None

class DSLParametric(BaseModel):
    version: int = Field(1, enum=[1])
    name: str
    connections: Dict[str, Any]
    consent: Optional[Dict[str, Any]] = None
    trigger: Dict[str, Any]
    actions: List[Dict[str, Any]]
    error_policy: Optional[Dict[str, Any]] = None
    observability: Optional[Dict[str, Any]] = None

# ============================================================================
# Frontend Models
# ============================================================================

class PlanRequest(BaseModel):
    user_id: str
    user_request: Optional[str] = None
    selected_apps: Optional[List[str]] = []
    num_suggestions: Optional[int] = Field(default=1, ge=1, le=5, description="Number of suggestions to generate (1-5)")

class Suggestion(BaseModel):
    suggestion_id: str
    title: str
    description: str
    dsl_parametric: DSLParametric
    missing_fields: List[MissingField]
    confidence: float = Field(..., ge=0, le=1)
    apps: List[str]
    source: str = Field(..., enum=["template", "generator"])
    full_workflow_json: Optional[Dict[str, Any]] = None

class PlanResponse(BaseModel):
    suggestions: List[Suggestion]

# ============================================================================
# Run Models
# ============================================================================

class RunCreate(BaseModel):
    workflow_id: str
    trigger_data: Optional[Dict[str, Any]] = None

class RunResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None

# User Models
class UserBase(BaseModel):
    """Base user model"""
    email: EmailStr

class UserCreate(UserBase):
    """User creation model"""
    pass

class User(UserBase):
    """User model with ID and timestamps"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class UserPreference(BaseModel):
    """User preference model"""
    preference_key: str
    preference_value: str

class UserPreferenceCreate(UserPreference):
    """User preference creation model"""
    user_id: UUID

class UserPreferenceResponse(UserPreference):
    """User preference response model"""
    id: int
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class UserWithPreferences(User):
    """User model with preferences"""
    preferences: Dict[str, str] = {}


