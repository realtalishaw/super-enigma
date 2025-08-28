"""
Main validator module for the Weave Linter & Validator Service
"""

import logging
import time
from typing import List, Dict, Any, Optional
from .models import (
    Stage, ValidateOptions, LintOptions, ValidationError, LintFinding,
    LintReport, ValidateResponse, CompileResponse, RepairRecord,
    LintContext, CompileContext
)
from .schema_validator import schema_validator
from .catalog_validator import catalog_validator
from .rules import rule_registry

logger = logging.getLogger(__name__)


async def validate(
    stage: Stage,
    doc: Dict[str, Any],
    opts: Optional[ValidateOptions] = None
) -> ValidateResponse:
    """
    Validate a workflow document for a specific stage
    
    Args:
        stage: The workflow stage to validate
        doc: The document to validate
        opts: Validation options
        
    Returns:
        Validation response with results
    """
    start_time = time.time()
    
    if opts is None:
        opts = ValidateOptions()
    
    logger.info(f"Starting validation for {stage.value} stage")
    
    errors = []
    
    try:
        # 1. JSON Schema validation (stage-specific to avoid cross-branch errors)
        schema_errors = schema_validator.validate_document_for_stage(stage, doc)
        errors.extend(schema_errors)
        
        # 2. Stage-specific validation
        stage_errors = await _validate_stage_specific(stage, doc, opts)
        errors.extend(stage_errors)
        
        # 3. Required fields validation
        required_errors = schema_validator.validate_required_fields(doc, stage)
        errors.extend(required_errors)
        
        # 4. Fast mode checks (if enabled)
        if opts.fast:
            fast_errors = await _fast_validation_checks(stage, doc)
            errors.extend(fast_errors)
        
        # Stop early if fail_fast is enabled and we have errors
        if opts.fail_fast and errors:
            logger.info(f"Validation failed early due to fail_fast option")
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        errors.append(ValidationError(
            code="VALIDATION_ERROR",
            path="root",
            message=f"Validation failed with error: {str(e)}",
            stage=stage
        ))
    
    validation_time = time.time() - start_time
    logger.info(f"Validation completed in {validation_time:.3f}s with {len(errors)} errors")
    
    return ValidateResponse(
        ok=len(errors) == 0,
        errors=errors
    )


async def lint(
    stage: Stage,
    doc: Dict[str, Any],
    context: LintContext,
    opts: Optional[LintOptions] = None
) -> LintReport:
    """
    Lint a workflow document for a specific stage
    
    Args:
        stage: The workflow stage to lint
        doc: The document to lint
        context: Linting context with catalog and connections
        opts: Linting options
        
    Returns:
        Linting report with findings
    """
    start_time = time.time()
    
    if opts is None:
        opts = LintOptions()
    
    logger.info(f"Starting linting for {stage.value} stage")
    
    errors = []
    warnings = []
    hints = []
    
    try:
        # 1. Rule-based linting
        rule_findings = await _apply_linting_rules(stage, doc, context, opts)
        
        # 2. Catalog validation
        catalog_findings = await catalog_validator.validate_toolkit_references(doc, context)
        
        # 3. Action parameter validation
        param_findings = await catalog_validator.validate_action_parameters(doc, context)
        
        # 4. Connection scope validation (for executable workflows)
        if stage == Stage.EXECUTABLE:
            scope_findings = await catalog_validator.validate_connection_scopes(doc, context)
            catalog_findings.extend(scope_findings)
        
        # 5. Categorize findings by severity
        for finding in rule_findings + catalog_findings + param_findings:
            if finding.severity == "ERROR":
                errors.append(finding)
            elif finding.severity == "WARNING":
                warnings.append(finding)
            elif finding.severity == "HINT":
                hints.append(finding)
        
        # 6. Apply max_findings limit
        if opts.max_findings:
            total_findings = len(errors) + len(warnings) + len(hints)
            if total_findings > opts.max_findings:
                logger.warning(f"Limiting findings to {opts.max_findings} (found {total_findings})")
                # Prioritize errors, then warnings, then hints
                if len(errors) > opts.max_findings:
                    errors = errors[:opts.max_findings]
                    warnings = []
                    hints = []
                elif len(errors) + len(warnings) > opts.max_findings:
                    warnings = warnings[:opts.max_findings - len(errors)]
                    hints = []
                else:
                    hints = hints[:opts.max_findings - len(errors) - len(warnings)]
        
    except Exception as e:
        logger.error(f"Linting error: {e}")
        errors.append(LintFinding(
            code="LINTING_ERROR",
            severity="ERROR",
            path="root",
            message=f"Linting failed with error: {str(e)}"
        ))
    
    linting_time = time.time() - start_time
    logger.info(f"Linting completed in {linting_time:.3f}s with {len(errors)} errors, {len(warnings)} warnings, {len(hints)} hints")
    
    return LintReport(
        errors=errors,
        warnings=warnings,
        hints=hints
    )


async def attempt_repair(
    stage: Stage,
    doc: Dict[str, Any],
    lint_report: LintReport
) -> Optional[Dict[str, Any]]:
    """
    Attempt to auto-repair fixable issues in a document
    
    Args:
        stage: The workflow stage
        doc: The document to repair
        lint_report: The linting report with findings
        
    Returns:
        Repaired document if repairs were applied, None otherwise
    """
    logger.info(f"Attempting auto-repair for {stage.value} stage")
    
    repairs_applied = []
    repaired_doc = doc.copy()
    
    # Only attempt repairs on ERROR findings that are auto-repairable
    for finding in lint_report.errors:
        rule = rule_registry.get_rule(finding.code)
        if rule and rule.auto_repairable and rule.repair:
            try:
                repair_result = rule.repair(repaired_doc, finding)
                if repair_result:
                    repairs_applied.append(RepairRecord(
                        rule_code=finding.code,
                        description=finding.message,
                        before_path=finding.path,
                        after_path=finding.path  # This could be enhanced to show actual changes
                    ))
                    logger.info(f"Applied auto-repair for rule {finding.code}")
            except Exception as e:
                logger.error(f"Failed to apply auto-repair for rule {finding.code}: {e}")
    
    if repairs_applied:
        logger.info(f"Applied {len(repairs_applied)} auto-repairs")
        return repaired_doc
    else:
        logger.info("No auto-repairs were applied")
        return None


async def validate_and_compile(
    concrete_doc: Dict[str, Any],
    context: CompileContext
) -> CompileResponse:
    """
    Validate and compile a concrete workflow document
    
    Args:
        concrete_doc: The concrete workflow document
        context: Compilation context
        
    Returns:
        Compilation response with results
    """
    logger.info("Starting validate-and-compile operation")
    
    # 1. Validate the executable document
    validation_result = await validate(Stage.EXECUTABLE, concrete_doc)
    if not validation_result.ok:
        return CompileResponse(
            ok=False,
            errors=validation_result.errors
        )
    
    # 2. Lint the executable document
    lint_result = await lint(Stage.EXECUTABLE, concrete_doc, context)
    
    # 3. Attempt auto-repair on repairable ERRORs only
    repaired_doc = None
    if any(finding.severity == "ERROR" for finding in lint_result.errors):
        repaired_doc = await attempt_repair(Stage.EXECUTABLE, concrete_doc, lint_result)
    
    # 4. Re-validate and re-lint if repaired
    if repaired_doc:
        logger.info("Document was repaired, re-validating and re-linting")
        validation_result = await validate(Stage.EXECUTABLE, repaired_doc)
        if not validation_result.ok:
            return CompileResponse(
                ok=False,
                errors=validation_result.errors
            )
        
        lint_result = await lint(Stage.EXECUTABLE, repaired_doc, context)
        doc_to_compile = repaired_doc
    else:
        doc_to_compile = concrete_doc
    
    # 5. Compile to DAG (placeholder for now)
    try:
        compiled_dag = await _compile_to_dag(doc_to_compile, context)
        
        # 6. Validate the compiled DAG
        dag_validation = await validate(Stage.DAG, compiled_dag)
        if not dag_validation.ok:
            return CompileResponse(
                ok=False,
                errors=dag_validation.errors
            )
        
        # 7. Lint the compiled DAG
        dag_lint = await lint(Stage.DAG, compiled_dag, context)
        
        return CompileResponse(
            ok=True,
            compiled=compiled_dag,
            lint=dag_lint
        )
        
    except Exception as e:
        logger.error(f"Compilation failed: {e}")
        return CompileResponse(
            ok=False,
            errors=[ValidationError(
                code="COMPILATION_ERROR",
                path="root",
                message=f"Compilation failed: {str(e)}",
                stage=Stage.DAG
            )]
        )


async def _validate_stage_specific(stage: Stage, doc: Dict[str, Any], opts: ValidateOptions) -> List[ValidationError]:
    """Apply stage-specific validation rules"""
    errors = []
    
    if stage == Stage.TEMPLATE:
        # Template-specific validation - be more lenient
        if "missing_information" not in doc:
            # Make this a warning instead of an error for templates
            logger.warning("Template missing 'missing_information' field - this is recommended but not required")
        
        # Check for basic workflow structure
        if "workflow" not in doc:
            errors.append(ValidationError(
                code="MISSING_WORKFLOW",
                path="workflow",
                message="Template must have a workflow section",
                stage=stage
            ))
        elif "name" not in doc["workflow"] or "description" not in doc["workflow"]:
            errors.append(ValidationError(
                code="MISSING_WORKFLOW_FIELDS",
                path="workflow",
                message="Workflow must have name and description",
                stage=stage
            ))
    
    elif stage == Stage.EXECUTABLE:
        # Executable-specific validation
        if "connections" not in doc:
            errors.append(ValidationError(
                code="MISSING_CONNECTIONS",
                path="connections",
                message="Executable workflow must specify connections",
                stage=stage
            ))
    
    elif stage == Stage.DAG:
        # DAG-specific validation
        if "nodes" not in doc or "edges" not in doc:
            errors.append(ValidationError(
                code="MISSING_DAG_STRUCTURE",
                path="",
                message="DAG must have both nodes and edges",
                stage=stage
            ))
    
    return errors


async def _fast_validation_checks(stage: Stage, doc: Dict[str, Any]) -> List[ValidationError]:
    """Fast validation checks for executor preflight"""
    errors = []
    
    # Basic structure checks that can be done quickly
    if not isinstance(doc, dict):
        errors.append(ValidationError(
            code="INVALID_DOCUMENT_TYPE",
            path="root",
            message="Document must be a JSON object",
            stage=stage
        ))
        return errors
    
    if "schema_type" not in doc:
        errors.append(ValidationError(
            code="MISSING_SCHEMA_TYPE",
            path="schema_type",
            message="Document must specify schema_type",
            stage=stage
        ))
    
    return errors


async def _apply_linting_rules(stage: Stage, doc: Dict[str, Any], context: LintContext, opts: LintOptions) -> List[LintFinding]:
    """Apply all applicable linting rules"""
    findings = []
    
    rules = rule_registry.get_rules_for_stage(stage)
    
    for rule in rules:
        try:
            if rule.applies(doc, context):
                rule_findings = rule.check(doc, context)
                findings.extend(rule_findings)
        except Exception as e:
            logger.error(f"Error applying rule {rule.id}: {e}")
            findings.append(LintFinding(
                code="RULE_ERROR",
                severity="ERROR",
                path="root",
                message=f"Rule {rule.id} failed: {str(e)}"
            ))
    
    return findings


async def _compile_to_dag(doc: Dict[str, Any], context: CompileContext) -> Dict[str, Any]:
    """Compile executable workflow to DAG format"""
    # This is a placeholder implementation
    # In a real system, this would:
    # 1. Convert actions to nodes
    # 2. Convert dependencies to edges
    # 3. Handle flow control (conditions, parallel execution)
    # 4. Generate execution graph
    
    logger.info("Compiling executable workflow to DAG")
    
    # Simple compilation for now
    dag = {
        "schema_type": "dag",
        "nodes": [],
        "edges": [],
        "metadata": {
            "name": doc.get("workflow", {}).get("name", "Compiled Workflow"),
            "description": doc.get("workflow", {}).get("description", ""),
            "compiled_from": "executable"
        }
    }
    
    # Convert actions to nodes
    if "workflow" in doc and "actions" in doc["workflow"]:
        for action in doc["workflow"]["actions"]:
            node = {
                "id": action.get("id", f"action_{len(dag['nodes'])}"),
                "type": "action",
                "data": {
                    "toolkit_slug": action.get("toolkit_slug"),
                    "action_name": action.get("action_name"),
                    "connection_id": action.get("connection_id")
                }
            }
            dag["nodes"].append(node)
    
    # Convert triggers to nodes
    if "workflow" in doc and "triggers" in doc["workflow"]:
        for trigger in doc["workflow"]["triggers"]:
            node = {
                "id": trigger.get("id", f"trigger_{len(dag['nodes'])}"),
                "type": "trigger",
                "data": {
                    "toolkit_slug": trigger.get("toolkit_slug"),
                    "composio_trigger_slug": trigger.get("composio_trigger_slug")
                }
            }
            dag["nodes"].append(node)
    
    # Create basic edges (simplified)
    if len(dag["nodes"]) > 1:
        for i in range(len(dag["nodes"]) - 1):
            edge = {
                "source": dag["nodes"][i]["id"],
                "target": dag["nodes"][i + 1]["id"]
            }
            dag["edges"].append(edge)
    
    return dag
