"""
Data models for the DSL LLM Generator service.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class GenerationRequest(BaseModel):
    """Request model for DSL generation"""
    
    user_prompt: str = Field(
        ..., 
        description="Natural language description of the desired workflow"
    )
    selected_apps: Optional[List[str]] = Field(
        default=None,
        description="Optional list of app/toolkit slugs to bias the generation"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID for personalization and tracking"
    )
    workflow_type: Optional[str] = Field(
        default="template",
        description="Type of workflow to generate: template, executable, or dag",
        enum=["template", "executable", "dag"]
    )
    complexity: Optional[str] = Field(
        default="medium",
        description="Desired complexity level",
        enum=["simple", "medium", "complex"]
    )


class MissingField(BaseModel):
    """Model for fields that need user input"""
    
    field: str = Field(..., description="Field name/path in the DSL")
    prompt: str = Field(..., description="Question to ask the user")
    type: str = Field(..., description="Expected data type")
    required: bool = Field(default=True, description="Whether this field is required")
    example: Optional[str] = Field(default=None, description="Example value")
    validation_rules: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Validation rules for this field"
    )


class GenerationResponse(BaseModel):
    """Response model for DSL generation"""
    
    success: bool = Field(..., description="Whether generation was successful")
    dsl_template: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Generated DSL template JSON"
    )
    missing_fields: List[MissingField] = Field(
        default_factory=list,
        description="Fields that need user input to complete the workflow"
    )
    confidence: float = Field(
        default=0.0,
        description="Confidence score (0.0 to 1.0) in the generated template"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Explanation of why this template was generated"
    )
    suggested_apps: Optional[List[str]] = Field(
        default=None,
        description="Apps that would be good for this workflow"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if generation failed"
    )
    generation_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata about the generation process"
    )
    raw_response: Optional[str] = Field(
        default=None,
        description="Raw LLM response text prior to parsing (for debugging/evals)"
    )
    is_exemplar: bool = Field(
        default=False,
        description="Whether this is an exemplar workflow for vague prompts"
    )
    exemplar_reason: Optional[str] = Field(
        default=None,
        description="Reason why an exemplar workflow was returned"
    )


class CatalogContext(BaseModel):
    """Context information from the catalog for generation"""
    
    available_providers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Available service providers"
    )
    available_triggers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Available trigger types"
    )
    available_actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Available action types"
    )
    provider_categories: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Provider categories for organization"
    )


class GenerationContext(BaseModel):
    """Full context for DSL generation"""
    
    request: GenerationRequest
    catalog: CatalogContext
    schema_definition: Dict[str, Any]
    user_preferences: Optional[Dict[str, Any]] = None
    workflow_templates: Optional[List[Dict[str, Any]]] = None
