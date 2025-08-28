"""
JSON Schema validation for workflow documents
"""

import json
import logging
from typing import List, Dict, Any, Optional
from jsonschema import validate, ValidationError as JSONSchemaValidationError
from jsonschema.validators import Draft202012Validator
from pathlib import Path

from .models import ValidationError, Stage

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validates workflow documents against the JSON schema"""
    
    def __init__(self, schema_path: Optional[str] = None):
        self.schema = None
        self.validator = None
        self._load_schema(schema_path)
    
    def _load_schema(self, schema_path: Optional[str] = None):
        """Load the JSON schema from file or use default path"""
        try:
            if schema_path is None:
                # Use default schema path relative to this file
                schema_path = Path(__file__).parent.parent / "dsl" / "schema.json"
            
            with open(schema_path, 'r') as f:
                self.schema = json.load(f)
            
            # Create validator instance
            self.validator = Draft202012Validator(self.schema)
            logger.info(f"Schema loaded successfully from {schema_path}")
            
        except Exception as e:
            logger.error(f"Failed to load schema from {schema_path}: {e}")
            raise
    
    def validate_document(self, doc: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate a document against the JSON schema
        
        Args:
            doc: The document to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        if not self.schema or not self.validator:
            raise RuntimeError("Schema not loaded")
        
        errors = []
        
        try:
            # Validate against the schema
            self.validator.validate(doc)
            
        except JSONSchemaValidationError as e:
            # Convert JSON Schema validation errors to our format
            errors.extend(self._convert_jsonschema_errors(e))
        
        return errors

    def validate_document_for_stage(self, stage: Stage, doc: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate a document against a specific stage's subschema only.
        This avoids cross-branch oneOf errors (e.g., executable/dag requirements) when validating templates.
        """
        if not self.schema:
            raise RuntimeError("Schema not loaded")
        errors = []
        try:
            stage_name = None
            if stage == Stage.TEMPLATE:
                stage_name = "TemplateSchema"
            elif stage == Stage.EXECUTABLE:
                stage_name = "ExecutableSchema"
            elif stage == Stage.DAG:
                stage_name = "DAGSchema"
            else:
                stage_name = "TemplateSchema"

            # Build a focused schema referencing only the stage subschema while preserving $defs
            focused_schema = {
                "$schema": self.schema.get("$schema", "https://json-schema.org/draft/2020-12/schema"),
                "$id": self.schema.get("$id", ""),
                "$ref": f"#/$defs/{stage_name}",
                "$defs": self.schema.get("$defs", {}),
            }

            # For template workflows, be more lenient with conditional logic
            if stage == Stage.TEMPLATE and "workflow" in doc and "flow_control" in doc.get("workflow", {}):
                # Temporarily remove flow_control for template validation to avoid strict schema errors
                workflow_copy = doc["workflow"].copy()
                if "flow_control" in workflow_copy:
                    del workflow_copy["flow_control"]
                doc_copy = doc.copy()
                doc_copy["workflow"] = workflow_copy
                
                validator = Draft202012Validator(focused_schema)
                validator.validate(doc_copy)
            else:
                validator = Draft202012Validator(focused_schema)
                validator.validate(doc)
                
        except JSONSchemaValidationError as e:
            errors.extend(self._convert_jsonschema_errors(e))
        except Exception as e:
            logging.getLogger(__name__).error(f"Stage validation error: {e}")
            errors.append(ValidationError(
                code="SCHEMA_VALIDATION_ERROR",
                path="root",
                message=str(e),
                stage=stage,
            ))
        return errors
    
    def _convert_jsonschema_errors(self, error: JSONSchemaValidationError) -> List[ValidationError]:
        """Convert JSON Schema validation errors to our format"""
        errors = []
        
        # Get the schema type from the document
        schema_type = self._get_schema_type(error.instance)
        stage = self._map_schema_type_to_stage(schema_type)
        
        # Convert the error
        meta = {
            "schema_path": list(error.schema_path),
            "validator": error.validator
        }
        
        # Add schema_value if it exists
        if hasattr(error, 'schema_value'):
            meta["schema_value"] = error.schema_value
        
        validation_error = ValidationError(
            code="SCHEMA_VALIDATION_ERROR",
            path=self._format_error_path(error.path),
            message=error.message,
            stage=stage,
            meta=meta
        )
        errors.append(validation_error)
        
        # Handle sub-errors recursively
        for sub_error in error.context:
            sub_errors = self._convert_jsonschema_errors(sub_error)
            errors.extend(sub_errors)
        
        return errors
    
    def _get_schema_type(self, instance: Any) -> Optional[str]:
        """Extract schema_type from the document instance"""
        if isinstance(instance, dict):
            return instance.get("schema_type")
        return None
    
    def _map_schema_type_to_stage(self, schema_type: Optional[str]) -> Stage:
        """Map schema_type string to Stage enum"""
        if schema_type == "template":
            return Stage.TEMPLATE
        elif schema_type == "executable":
            return Stage.EXECUTABLE
        elif schema_type == "dag":
            return Stage.DAG
        else:
            # Default to template if unknown
            return Stage.TEMPLATE
    
    def _format_error_path(self, path: List[str]) -> str:
        """Format the error path for display"""
        if not path:
            return "root"
        
        formatted_path = ""
        for i, part in enumerate(path):
            if isinstance(part, int):
                formatted_path += f"[{part}]"
            else:
                if i == 0:
                    formatted_path += part
                else:
                    formatted_path += f".{part}"
        
        return formatted_path
    
    def get_schema_info(self) -> Dict[str, Any]:
        """Get information about the loaded schema"""
        if not self.schema:
            return {}
        
        return {
            "title": self.schema.get("title"),
            "description": self.schema.get("description"),
            "id": self.schema.get("$id"),
            "schema": self.schema.get("$schema"),
            "supported_types": ["template", "executable", "dag"]
        }
    
    def is_valid_stage(self, doc: Dict[str, Any]) -> bool:
        """Check if the document has a valid schema_type"""
        schema_type = doc.get("schema_type")
        return schema_type in ["template", "executable", "dag"]
    
    def get_required_fields(self, stage: Stage) -> List[str]:
        """Get required fields for a specific stage"""
        if not self.schema:
            return []
        
        stage_name = stage.value.capitalize() + "Schema"
        stage_def = self.schema.get("$defs", {}).get(stage_name, {})
        
        return stage_def.get("required", [])
    
    def validate_required_fields(self, doc: Dict[str, Any], stage: Stage) -> List[ValidationError]:
        """Validate that all required fields are present for a stage"""
        errors = []
        required_fields = self.get_required_fields(stage)
        
        # For template workflows, be more lenient with missing_information
        if stage == Stage.TEMPLATE and "missing_information" not in required_fields:
            required_fields = ["schema_type", "workflow"]  # Only require essential fields
        
        for field in required_fields:
            if field not in doc:
                # For template workflows, make missing_information a warning
                if stage == Stage.TEMPLATE and field == "missing_information":
                    logger.warning(f"Template missing recommended field '{field}' - this is recommended but not required")
                    continue
                    
                errors.append(ValidationError(
                    code="MISSING_REQUIRED_FIELD",
                    path=field,
                    message=f"Required field '{field}' is missing for {stage.value} stage",
                    stage=stage
                ))
        
        return errors


# Global schema validator instance
schema_validator = SchemaValidator()
