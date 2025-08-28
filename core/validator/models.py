"""
Type definitions for the Weave Linter & Validator Service
"""

from typing import List, Dict, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass


class Stage(str, Enum):
    """Workflow specification stages"""
    TEMPLATE = "template"
    EXECUTABLE = "executable"
    DAG = "dag"


@dataclass
class ValidateOptions:
    """Options for validation operations"""
    fast: bool = False
    fail_fast: bool = False


@dataclass
class LintOptions:
    """Options for linting operations"""
    level: str = "standard"  # "standard" | "strict"
    max_findings: int = 100


@dataclass
class ValidationError:
    """A validation error that prevents execution"""
    code: str
    path: str
    message: str
    stage: Stage
    meta: Optional[Dict[str, Any]] = None


@dataclass
class LintFinding:
    """A linting finding (warning, hint, or error)"""
    code: str
    severity: str  # "ERROR" | "WARNING" | "HINT"
    path: str
    message: str
    hint: Optional[str] = None
    docs: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


@dataclass
class LintReport:
    """Complete linting report"""
    errors: List[LintFinding]
    warnings: List[LintFinding]
    hints: List[LintFinding]


@dataclass
class ValidateResponse:
    """Response from validation operation"""
    ok: bool
    errors: List[ValidationError]


@dataclass
class CompileResponse:
    """Response from validate-and-compile operation"""
    ok: bool
    compiled: Optional[Any] = None
    errors: Optional[List[ValidationError]] = None
    lint: Optional[LintReport] = None


@dataclass
class RepairRecord:
    """Record of an auto-repair operation"""
    rule_code: str
    description: str
    before_path: str
    after_path: str


# Context interfaces
class Catalog:
    """In-memory provider/actions/params/scopes"""
    pass


class Connections:
    """Map connection_id -> scopes/status"""
    pass


@dataclass
class LintContext:
    """Context for linting operations"""
    catalog: Catalog
    connections: Optional[Connections] = None
    tenant_config: Optional[Dict[str, Any]] = None


@dataclass
class CompileContext(LintContext):
    """Context for compilation operations"""
    compiler_flags: Optional[Dict[str, Any]] = None


# Rule definitions
@dataclass
class Rule:
    """A validation or linting rule"""
    id: str
    stage: List[Stage]
    severity: str
    message: str
    docs: str
    auto_repairable: bool
    applies: callable
    check: callable
    repair: Optional[callable] = None
