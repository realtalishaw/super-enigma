"""
Validation and linting rules for the Weave Linter & Validator Service
"""

import json
from typing import List, Dict, Any, Optional
from .models import Rule, Stage, LintFinding, ValidationError, LintContext


class RuleRegistry:
    """Registry for validation and linting rules"""
    
    def __init__(self):
        self.rules: Dict[str, Rule] = {}
        self._register_core_rules()
    
    def register_rule(self, rule: Rule):
        """Register a new rule"""
        self.rules[rule.id] = rule
    
    def get_rules_for_stage(self, stage: Stage) -> List[Rule]:
        """Get all rules that apply to a specific stage"""
        return [rule for rule in self.rules.values() if stage in rule.stage]
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get a specific rule by ID"""
        return self.rules.get(rule_id)
    
    def _register_core_rules(self):
        """Register all core validation and linting rules"""
        # This method will be called by create_rule_registry() to populate the registry
        pass


# Core rule implementations
def _check_unknown_tool(doc: Dict[str, Any], catalog: Any) -> List[LintFinding]:
    """Check for unknown tools/actions in the workflow"""
    findings = []
    
    if "workflow" not in doc or "actions" not in doc["workflow"]:
        return findings
    
    for action in doc["workflow"]["actions"]:
        toolkit_slug = action.get("toolkit_slug")
        action_name = action.get("action_name")
        
        if not toolkit_slug or not action_name:
            continue
            
        # TODO: Implement actual catalog lookup
        # For now, we'll just check if the fields exist
        if not toolkit_slug or not action_name:
            findings.append(LintFinding(
                code="E001",
                severity="ERROR",
                path=f"workflow.actions[].toolkit_slug",
                message=f"Unknown toolkit/action: {toolkit_slug}/{action_name}",
                hint="Ensure the toolkit and action exist in the catalog"
            ))
    
    return findings


def _check_param_spec_mismatch(doc: Dict[str, Any], catalog: Any) -> List[LintFinding]:
    """Check for parameter specification mismatches"""
    findings = []
    
    if "workflow" not in doc or "actions" not in doc["workflow"]:
        return findings
    
    for action in doc["workflow"]["actions"]:
        if "required_inputs" not in action:
            continue
            
        for input_param in action["required_inputs"]:
            param_name = input_param.get("name")
            param_type = input_param.get("type")
            
            if not param_name:
                findings.append(LintFinding(
                    code="E002",
                    severity="ERROR",
                    path="workflow.actions[].required_inputs[].name",
                    message="Missing parameter name",
                    hint="All input parameters must have a name"
                ))
            
            if not param_type:
                findings.append(LintFinding(
                    code="E002",
                    severity="ERROR",
                    path="workflow.actions[].required_inputs[].type",
                    message="Missing parameter type",
                    hint="All input parameters must have a type"
                ))
    
    return findings


def _check_scope_missing(doc: Dict[str, Any], context: LintContext) -> List[LintFinding]:
    """Check for missing scopes in executable workflows"""
    findings = []
    
    if doc.get("schema_type") != "executable":
        return findings
    
    if "workflow" not in doc or "actions" not in doc["workflow"]:
        return findings
    
    for action in doc["workflow"]["actions"]:
        if action.get("requires_auth", True) and not action.get("connection_id"):
            findings.append(LintFinding(
                code="E004",
                severity="ERROR",
                path=f"workflow.actions[].connection_id",
                message=f"Action {action.get('id', 'unknown')} requires authentication but no connection_id provided",
                hint="Provide a connection_id for authenticated actions"
            ))
    
    return findings


def _check_trigger_id_missing(doc: Dict[str, Any], context: LintContext) -> List[LintFinding]:
    """Check for missing trigger IDs in executable workflows"""
    findings = []
    
    if doc.get("schema_type") != "executable":
        return findings
    
    if "workflow" not in doc or "triggers" not in doc["workflow"]:
        return findings
    
    for trigger in doc["workflow"]["triggers"]:
        if not trigger.get("composio_trigger_slug"):
            findings.append(LintFinding(
                code="E010",
                severity="ERROR",
                path="workflow.triggers[].composio_trigger_slug",
                message=f"Trigger {trigger.get('id', 'unknown')} missing composio_trigger_slug",
                hint="Executable workflows must have concrete trigger slugs"
            ))
    
    return findings


def _check_connection_references(doc: Dict[str, Any], context: LintContext) -> List[LintFinding]:
    """Check that referenced connections exist"""
    findings = []
    
    if doc.get("schema_type") != "executable":
        return findings
    
    if "connections" not in doc:
        findings.append(LintFinding(
            code="E004",
            severity="ERROR",
            path="connections",
            message="Executable workflow must specify required connections",
            hint="Add connections array with required toolkit connections"
        ))
        return findings
    
    # Check that all actions reference valid connections
    if "workflow" in doc and "actions" in doc["workflow"]:
        for action in doc["workflow"]["actions"]:
            if action.get("requires_auth", True):
                connection_id = action.get("connection_id")
                if not connection_id:
                    findings.append(LintFinding(
                        code="E004",
                        severity="ERROR",
                        path=f"workflow.actions[].connection_id",
                        message=f"Action {action.get('id', 'unknown')} requires connection_id",
                        hint="Provide connection_id for authenticated actions"
                    ))
                else:
                    # Check if connection exists in connections array
                    connection_found = False
                    for conn in doc["connections"]:
                        if conn.get("connection_id") == connection_id and conn.get("toolkit_slug") == action.get("toolkit_slug"):
                            connection_found = True
                            break
                    
                    if not connection_found:
                        findings.append(LintFinding(
                            code="E004",
                            severity="ERROR",
                            path=f"workflow.actions[].connection_id",
                            message=f"Connection {connection_id} not found in connections array",
                            hint="Ensure connection_id matches an entry in the connections array"
                        ))
    
    return findings


def _check_graph_integrity(doc: Dict[str, Any], context: LintContext) -> List[LintFinding]:
    """Check DAG graph integrity"""
    findings = []
    
    if doc.get("schema_type") != "dag":
        return findings
    
    if "nodes" not in doc or "edges" not in doc:
        findings.append(LintFinding(
            code="E006",
            severity="ERROR",
            path="",
            message="DAG must have both nodes and edges",
            hint="Ensure nodes and edges arrays are present"
        ))
        return findings
    
    # Check for unique node IDs
    node_ids = set()
    for node in doc["nodes"]:
        node_id = node.get("id")
        if not node_id:
            findings.append(LintFinding(
                code="E006",
                severity="ERROR",
                path="nodes[].id",
                message="Node missing ID",
                hint="All nodes must have unique IDs"
            ))
        elif node_id in node_ids:
            findings.append(LintFinding(
                code="E006",
                severity="ERROR",
                path="nodes[].id",
                message=f"Duplicate node ID: {node_id}",
                hint="All node IDs must be unique"
            ))
        else:
            node_ids.add(node_id)
    
    # Check edge references
    for edge in doc["edges"]:
        source = edge.get("source")
        target = edge.get("target")
        
        if source not in node_ids:
            findings.append(LintFinding(
                code="E008",
                severity="ERROR",
                path="edges[].source",
                message=f"Edge source node {source} not found",
                hint="All edge sources must reference existing nodes"
            ))
        
        if target not in node_ids:
            findings.append(LintFinding(
                code="E008",
                severity="ERROR",
                path="edges[].target",
                message=f"Edge target node {target} not found",
                hint="All edge targets must reference existing nodes"
            ))
    
    return findings


def _check_cycle_in_graph(doc: Dict[str, Any], context: LintContext) -> List[LintFinding]:
    """Check for cycles in the DAG"""
    findings = []
    
    if doc.get("schema_type") != "dag":
        return findings
    
    # Simple cycle detection - this could be enhanced with more sophisticated algorithms
    if "edges" in doc:
        edges = doc["edges"]
        if len(edges) > 0:
            # For now, just check for self-loops
            for edge in edges:
                if edge.get("source") == edge.get("target"):
                    findings.append(LintFinding(
                        code="E006",
                        severity="ERROR",
                        path="edges[]",
                        message=f"Self-loop detected: {edge.get('source')} -> {edge.get('target')}",
                        hint="Remove self-loops from the workflow"
                    ))
    
    return findings


# Rule registration
def create_rule_registry() -> RuleRegistry:
    """Create and populate the rule registry"""
    registry = RuleRegistry()
    
    # Catalog & Tooling Rules
    registry.register_rule(Rule(
        id="E001",
        stage=[Stage.TEMPLATE, Stage.EXECUTABLE],
        severity="ERROR",
        message="Unknown provider/action/trigger",
        docs="/rules/E001",
        auto_repairable=False,
        applies=lambda doc, ctx: True,
        check=_check_unknown_tool
    ))
    
    registry.register_rule(Rule(
        id="E002",
        stage=[Stage.TEMPLATE, Stage.EXECUTABLE],
        severity="ERROR",
        message="Parameter specification mismatch",
        docs="/rules/E002",
        auto_repairable=False,
        applies=lambda doc, ctx: True,
        check=_check_param_spec_mismatch
    ))
    
    registry.register_rule(Rule(
        id="E004",
        stage=[Stage.EXECUTABLE],
        severity="ERROR",
        message="Missing required scopes/connections",
        docs="/rules/E004",
        auto_repairable=False,
        applies=lambda doc, ctx: doc.get("schema_type") == "executable",
        check=_check_scope_missing
    ))
    
    registry.register_rule(Rule(
        id="E010",
        stage=[Stage.EXECUTABLE],
        severity="ERROR",
        message="Missing trigger ID",
        docs="/rules/E010",
        auto_repairable=False,
        applies=lambda doc, ctx: doc.get("schema_type") == "executable",
        check=_check_trigger_id_missing
    ))
    
    # Graph & Dataflow Rules
    registry.register_rule(Rule(
        id="E006",
        stage=[Stage.DAG],
        severity="ERROR",
        message="Graph integrity violation",
        docs="/rules/E006",
        auto_repairable=False,
        applies=lambda doc, ctx: doc.get("schema_type") == "dag",
        check=_check_graph_integrity
    ))
    
    registry.register_rule(Rule(
        id="E008",
        stage=[Stage.DAG],
        severity="ERROR",
        message="Unresolved reference",
        docs="/rules/E008",
        auto_repairable=False,
        applies=lambda doc, ctx: doc.get("schema_type") == "dag",
        check=lambda doc, ctx: _check_graph_integrity(doc, ctx)  # Reuse graph integrity check
    ))
    
    # Connection validation
    registry.register_rule(Rule(
        id="E004",
        stage=[Stage.EXECUTABLE],
        severity="ERROR",
        message="Invalid connection references",
        docs="/rules/E004",
        auto_repairable=False,
        applies=lambda doc, ctx: doc.get("schema_type") == "executable",
        check=_check_connection_references
    ))
    
    # Cycle detection
    registry.register_rule(Rule(
        id="E006",
        stage=[Stage.DAG],
        severity="ERROR",
        message="Cycle detected in graph",
        docs="/rules/E006",
        auto_repairable=False,
        applies=lambda doc, ctx: doc.get("schema_type") == "dag",
        check=_check_cycle_in_graph
    ))
    
    return registry


# Global rule registry instance
rule_registry = create_rule_registry()
