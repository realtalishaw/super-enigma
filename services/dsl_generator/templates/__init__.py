"""
Templates package for DSL Generator prompts.

Contains prompt templates for different workflow types and complexity levels.
"""

from .base_templates import (
    EXECUTABLE_PROMPT,
    DAG_PROMPT,
    render_template_prompt,
    CATALOG_VALIDATION_STRICT_XML,
    render_feedback_retry,
    render_final_attempt,
    COMPLEXITY_GUIDANCE_TEXT,
    DSL_SCHEMA_V2,
)

__all__ = [
    'EXECUTABLE_PROMPT',
    'DAG_PROMPT',
    'render_template_prompt',
    'CATALOG_VALIDATION_STRICT_XML',
    'render_feedback_retry',
    'render_final_attempt',
    'COMPLEXITY_GUIDANCE_TEXT',
    'DSL_SCHEMA_V2',
]
