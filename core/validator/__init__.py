"""
Weave Linter & Validator Service

A comprehensive validation and linting service for Template, Executable, and DAG workflow specifications.
"""

from .validator import (
    validate,
    lint,
    attempt_repair,
    validate_and_compile
)
from .models import (
    Stage,
    ValidateOptions,
    LintOptions,
    ValidationError,
    LintFinding,
    LintReport,
    ValidateResponse,
    CompileResponse,
    RepairRecord,
    LintContext,
    CompileContext,
    Catalog,
    Connections
)
from .json_output import (
    validation_to_json,
    lint_to_json,
    compile_to_json,
    comprehensive_to_json,
    JSONFormatter
)

__version__ = "1.0.0"
__all__ = [
    "validate",
    "lint", 
    "attempt_repair",
    "validate_and_compile",
    "Stage",
    "ValidateOptions",
    "LintOptions",
    "ValidationError",
    "LintFinding",
    "LintReport",
    "ValidateResponse",
    "CompileResponse",
    "RepairRecord",
    "LintContext",
    "CompileContext",
    "Catalog",
    "Connections",
    "validation_to_json",
    "lint_to_json",
    "compile_to_json",
    "comprehensive_to_json",
    "JSONFormatter"
]
