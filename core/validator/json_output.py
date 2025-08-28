"""
JSON output formatting for the Weave Linter & Validator Service
"""

import json
from typing import Dict, Any, List
from datetime import datetime
from .models import (
    ValidationError, LintFinding, LintReport, 
    ValidateResponse, CompileResponse, Stage
)


class JSONFormatter:
    """Formats validation and linting results as structured JSON"""
    
    @staticmethod
    def format_validation_response(response: ValidateResponse) -> Dict[str, Any]:
        """Format validation response as JSON"""
        return {
            "success": response.ok,
            "timestamp": datetime.utcnow().isoformat(),
            "stage": "validation",
            "errors": [
                {
                    "code": error.code,
                    "path": error.path,
                    "message": error.message,
                    "stage": error.stage.value if hasattr(error.stage, 'value') else str(error.stage),
                    "meta": error.meta or {}
                }
                for error in response.errors
            ],
            "summary": {
                "total_errors": len(response.errors),
                "validation_passed": response.ok
            }
        }
    
    @staticmethod
    def format_lint_report(report: LintReport) -> Dict[str, Any]:
        """Format linting report as JSON"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "stage": "linting",
            "findings": {
                "errors": [
                    {
                        "code": finding.code,
                        "path": finding.path,
                        "message": finding.message,
                        "severity": finding.severity,
                        "hint": finding.hint,
                        "docs": finding.docs,
                        "meta": finding.meta or {}
                    }
                    for finding in report.errors
                ],
                "warnings": [
                    {
                        "code": finding.code,
                        "path": finding.path,
                        "message": finding.message,
                        "severity": finding.severity,
                        "hint": finding.hint,
                        "docs": finding.docs,
                        "meta": finding.meta or {}
                    }
                    for finding in report.warnings
                ],
                "hints": [
                    {
                        "code": finding.code,
                        "path": finding.path,
                        "message": finding.message,
                        "severity": finding.severity,
                        "hint": finding.hint,
                        "docs": finding.docs,
                        "meta": finding.meta or {}
                    }
                    for finding in report.hints
                ]
            },
            "summary": {
                "total_errors": len(report.errors),
                "total_warnings": len(report.warnings),
                "total_hints": len(report.hints),
                "has_errors": len(report.errors) > 0,
                "has_warnings": len(report.warnings) > 0,
                "has_hints": len(report.hints) > 0
            }
        }
    
    @staticmethod
    def format_compile_response(response: CompileResponse) -> Dict[str, Any]:
        """Format compilation response as JSON"""
        result = {
            "success": response.ok,
            "timestamp": datetime.utcnow().isoformat(),
            "stage": "compilation"
        }
        
        if response.ok and response.compiled:
            result["compiled_workflow"] = {
                "type": "dag",
                "nodes_count": len(response.compiled.get("nodes", [])),
                "edges_count": len(response.compiled.get("edges", [])),
                "structure": response.compiled
            }
        
        if response.errors:
            result["errors"] = [
                {
                    "code": error.code,
                    "path": error.path,
                    "message": error.message,
                    "stage": error.stage.value if hasattr(error.stage, 'value') else str(error.stage),
                    "meta": error.meta or {}
                }
                for error in response.errors
            ]
        
        if response.lint:
            result["lint_report"] = JSONFormatter.format_lint_report(response.lint)
        
        result["summary"] = {
            "compilation_successful": response.ok,
            "total_errors": len(response.errors) if response.errors else 0,
            "has_compiled_workflow": response.ok and response.compiled is not None
        }
        
        return result
    
    @staticmethod
    def format_comprehensive_report(
        validation_result: ValidateResponse,
        lint_result: LintReport,
        compile_result: CompileResponse = None
    ) -> Dict[str, Any]:
        """Format a comprehensive validation, linting, and compilation report"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "workflow_analysis": {
                "validation": JSONFormatter.format_validation_response(validation_result),
                "linting": JSONFormatter.format_lint_report(lint_result)
            },
            "compilation": JSONFormatter.format_compile_response(compile_result) if compile_result else None,
            "overall_summary": {
                "workflow_valid": validation_result.ok,
                "has_lint_errors": len(lint_result.errors) > 0,
                "has_lint_warnings": len(lint_result.warnings) > 0,
                "compilation_successful": compile_result.ok if compile_result else None,
                "ready_for_execution": (
                    validation_result.ok and 
                    len(lint_result.errors) == 0 and 
                    (compile_result.ok if compile_result else True)
                )
            }
        }
    
    @staticmethod
    def to_json_string(data: Dict[str, Any], pretty: bool = False) -> str:
        """Convert data to JSON string"""
        if pretty:
            return json.dumps(data, indent=2, default=str)
        return json.dumps(data, default=str)
    
    @staticmethod
    def save_to_file(data: Dict[str, Any], filename: str, pretty: bool = True) -> None:
        """Save JSON data to file"""
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2 if pretty else None, default=str)


# Convenience functions for easy JSON output
def validation_to_json(response: ValidateResponse, pretty: bool = False) -> str:
    """Convert validation response to JSON string"""
    return JSONFormatter.to_json_string(
        JSONFormatter.format_validation_response(response), 
        pretty=pretty
    )


def lint_to_json(report: LintReport, pretty: bool = False) -> str:
    """Convert linting report to JSON string"""
    return JSONFormatter.to_json_string(
        JSONFormatter.format_lint_report(report), 
        pretty=pretty
    )


def compile_to_json(response: CompileResponse, pretty: bool = False) -> str:
    """Convert compilation response to JSON string"""
    return JSONFormatter.to_json_string(
        JSONFormatter.format_compile_response(response), 
        pretty=pretty
    )


def comprehensive_to_json(
    validation_result: ValidateResponse,
    lint_result: LintReport,
    compile_result: CompileResponse = None,
    pretty: bool = False
) -> str:
    """Convert comprehensive results to JSON string"""
    data = JSONFormatter.format_comprehensive_report(
        validation_result, lint_result, compile_result
    )
    return JSONFormatter.to_json_string(data, pretty=pretty)


def comprehensive_to_dict(
    validation_result: ValidateResponse,
    lint_result: LintReport,
    compile_result: CompileResponse = None
) -> dict:
    """Convert comprehensive results to Python dict"""
    return JSONFormatter.format_comprehensive_report(
        validation_result, lint_result, compile_result
    )
