"""
Base compiler class with common functionality and interfaces.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
import hashlib
import logging

logger = logging.getLogger(__name__)


@dataclass
class CompilerReport:
    """Report from compiler operations"""
    errors: List[Dict[str, Any]] = None
    warnings: List[Dict[str, Any]] = None
    repairs: List[Dict[str, Any]] = None
    artifact_refs: List[str] = None
    hints: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.repairs is None:
            self.repairs = []
        if self.artifact_refs is None:
            self.artifact_refs = []
        if self.hints is None:
            self.hints = []
    
    def add_error(self, code: str, path: str, message: str, hint: Optional[str] = None):
        """Add an error to the report"""
        self.errors.append({
            "code": code,
            "path": path,
            "message": message,
            "hint": hint
        })
    
    def add_warning(self, code: str, path: str, message: str, hint: Optional[str] = None):
        """Add a warning to the report"""
        self.warnings.append({
            "code": code,
            "path": path,
            "message": message,
            "hint": hint
        })
    
    def add_repair(self, path: str, original: Any, repaired: Any, reason: str):
        """Add a repair to the report"""
        self.repairs.append({
            "path": path,
            "original": original,
            "repaired": repaired,
            "reason": reason
        })
    
    def add_hint(self, hint: str):
        """Add a hint to the report"""
        self.hints.append(hint)
    
    @property
    def has_errors(self) -> bool:
        """Check if there are any errors"""
        return len(self.errors) > 0
    
    @property
    def is_success(self) -> bool:
        """Check if compilation was successful"""
        return not self.has_errors


class BaseCompiler(ABC):
    """Base class for all compilers"""
    
    def __init__(self):
        self.report = CompilerReport()
    
    @abstractmethod
    def compile(self, input_doc: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Main compilation method - must be implemented by subclasses"""
        pass
    
    def _generate_id(self, prefix: str, sequence: int) -> str:
        """Generate a stable ID for nodes"""
        return f"{prefix}{sequence}"
    
    def _hash_trigger_instance(self, user_id: str, workflow_id: str, version: str, local_id: str) -> str:
        """Generate deterministic trigger instance ID"""
        content = f"{user_id}:{workflow_id}:{version}:{local_id}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _safe_render_placeholder(self, template: str, answers: Dict[str, Any]) -> str:
        """Safely render placeholders without code execution"""
        if not isinstance(template, str):
            return template
        
        try:
            # Simple placeholder replacement - no eval or code execution
            result = template
            for key, value in answers.items():
                placeholder = f"{{{{{key}}}}}"
                if placeholder in result:
                    result = result.replace(placeholder, str(value))
            return result
        except Exception as e:
            logger.warning(f"Failed to render placeholder in template: {e}")
            return template
    
    def _validate_required_fields(self, doc: Dict[str, Any], required_fields: List[str], path: str = "") -> bool:
        """Validate that required fields are present"""
        for field in required_fields:
            if field not in doc:
                self.report.add_error(
                    "MISSING_REQUIRED_FIELD",
                    f"{path}.{field}" if path else field,
                    f"Required field '{field}' is missing"
                )
                return False
        return True
    
    def _get_nested_value(self, doc: Dict[str, Any], path: str, default: Any = None) -> Any:
        """Get a nested value from a document using dot notation"""
        try:
            keys = path.split('.')
            current = doc
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            return current
        except Exception:
            return default
    
    def _set_nested_value(self, doc: Dict[str, Any], path: str, value: Any) -> bool:
        """Set a nested value in a document using dot notation"""
        try:
            keys = path.split('.')
            current = doc
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            current[keys[-1]] = value
            return True
        except Exception:
            return False
