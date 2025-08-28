"""
DSL Generator Package

A modular workflow DSL generation service using Claude AI.
"""

from .generator import DSLGeneratorService
from .catalog_manager import CatalogManager
from .context_builder import ContextBuilder
from .prompt_builder import PromptBuilder
from .ai_client import AIClient
from .response_parser import ResponseParser
from .workflow_validator import WorkflowValidator
from .models import (
    GenerationRequest, 
    GenerationResponse, 
    MissingField,
    CatalogContext, 
    GenerationContext
)
# Template exports are intentionally omitted from package root to avoid tight coupling

__all__ = [
    'DSLGeneratorService',
    'CatalogManager',
    'ContextBuilder',
    'PromptBuilder',
    'AIClient',
    'ResponseParser',
    'WorkflowValidator',
    'GenerationRequest',
    'GenerationResponse',
    'MissingField',
    'CatalogContext',
    'GenerationContext',
]
