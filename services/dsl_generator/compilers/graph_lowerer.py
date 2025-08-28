"""
Graph Lowerer (E→D)

Turns concrete steps and flow-control intent into an executable graph with explicit 
node types, edges, routing conditions, parallelism, joins, and loop constructs. 
Adds optional UI metadata for React Flow.
"""

import copy
import logging
from typing import Dict, Any, List, Optional, Tuple
from base import BaseCompiler, CompilerReport

logger = logging.getLogger(__name__)


class GraphLowerer(BaseCompiler):
    """
    Graph Lowerer: Executable JSON → DAG JSON
    
    Creates an executable graph with:
    - Explicit node types (trigger, action, gateway, parallel, join, loop)
    - Edges with routing conditions
    - Parallelism and joins
    - Loop constructs
    - UI metadata for React Flow
    """
    
    def __init__(self):
        super().__init__()
        self.node_counter = {"t": 0, "a": 0, "g": 0, "par": 0, "join": 0, "loop": 0}
        self.index = {
            "triggerMap": {},
            "actionMap": {},
            "gatewayMap": {},
            "parallelMap": {},
            "joinMap": {},
            "loopMap": {}
        }
    
    def compile(self, executable_doc: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main compilation method for Executable → DAG
        
        Args:
            executable_doc: Executable JSON document
            ctx: Context containing catalog, layout options, uiDefaults
            
        Returns:
            Dict with dag_doc and report
        """
        self.report = CompilerReport()
        self.node_counter = {"t": 0, "a": 0, "g": 0, "par": 0, "join": 0, "loop": 0}
        self.index = {
            "triggerMap": {},
            "actionMap": {},
            "gatewayMap": {},
            "parallelMap": {},
            "joinMap": {},
            "loopMap": {}
        }
        
        try:
            # 1) Validate executable
            if not self._validate_executable(executable_doc):
                return {"dag_doc": None, "report": self.report}
            
            # 2) Initialize graph
            G = self._init_graph(executable_doc)
            
            # 3) Emit trigger nodes
            self._emit_trigger_nodes(G, executable_doc, ctx)
            
            # 4) Emit action nodes
            self._emit_action_nodes(G, executable_doc, ctx)
            
            # 5) Lower flow control
            self._lower_flow_control(G, executable_doc, ctx)
            
            # 6) Add linear/routed edges
            self._add_routed_edges(G, executable_doc)
            
            # 7) Compute globals and UI
            self._compute_globals_and_ui(G, executable_doc, ctx)
            
            # 8) Final validation
            if not self._validate_dag(G):
                return {"dag_doc": None, "report": self.report}
            
            return {
                "dag_doc": G,
                "report": self.report
            }
            
        except Exception as e:
            logger.error(f"Graph lowering failed: {e}")
            self.report.add_error(
                "INTERNAL_ERROR",
                "",
                f"Internal error during graph lowering: {str(e)}"
            )
            return {"dag_doc": None, "report": self.report}
    
    def _validate_executable(self, executable_doc: Dict[str, Any]) -> bool:
        """Validate executable document structure"""
        required_fields = ["workflow_id", "version", "triggers", "actions"]
        
        if not self._validate_required_fields(executable_doc, required_fields):
            return False
        
        # Validate that all triggers and actions have exec blocks
        for trigger in executable_doc.get("triggers", []):
            if "exec" not in trigger:
                self.report.add_error(
                    "MISSING_EXEC_BLOCK",
                    f"triggers.{trigger.get('local_id')}",
                    "Trigger missing executable configuration"
                )
                return False
        
        for action in executable_doc.get("actions", []):
            if "exec" not in action:
                self.report.add_error(
                    "MISSING_EXEC_BLOCK",
                    f"actions.{action.get('local_id')}",
                    "Action missing executable configuration"
                )
                return False
        
        return True
    
    def _init_graph(self, executable_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize the DAG graph structure"""
        return {
            "workflow_id": executable_doc["workflow_id"],
            "version": executable_doc["version"],
            "user_id": executable_doc.get("user_id"),
            "nodes": [],
            "edges": [],
            "globals": {},
            "ui": {
                "layout": "dagre",
                "viewport": {"x": 0, "y": 0, "zoom": 1}
            }
        }
    
    def _emit_trigger_nodes(self, G: Dict[str, Any], executable_doc: Dict[str, Any], ctx: Dict[str, Any]):
        """Emit trigger nodes in the graph"""
        for trigger in executable_doc.get("triggers", []):
            nid = self._new_node_id("t")
            
            # Determine trigger kind
            trigger_type = trigger.get("type", "event")
            kind = "schedule_based" if trigger_type == "scheduled" else "event_based"
            
            node_data = {
                "kind": kind,
                "tool": trigger["exec"]["provider"],
                "slug": trigger["exec"]["trigger_slug"],
                "connection_id": trigger["exec"]["connection_id"],
                "configuration": trigger["exec"]["configuration"]
            }
            
            # Add schedule info if it's a scheduled trigger
            if trigger_type == "scheduled" and "schedule" in trigger:
                node_data["schedule"] = trigger["schedule"]
            
            node = {
                "id": nid,
                "type": "trigger",
                "data": node_data,
                "label": self._ui_label("Trigger", trigger),
                "icon": self._icon_for(trigger, ctx)
            }
            
            G["nodes"].append(node)
            self.index["triggerMap"][trigger["local_id"]] = nid
    
    def _emit_action_nodes(self, G: Dict[str, Any], executable_doc: Dict[str, Any], ctx: Dict[str, Any]):
        """Emit action nodes in the graph"""
        for action in executable_doc.get("actions", []):
            nid = self._new_node_id("a")
            
            node_data = {
                "tool": action["exec"]["provider"],
                "action": action["exec"]["action_slug"],
                "connection_id": action["exec"]["connection_id"],
                "input_template": self._build_input_template(action, ctx),
                "output_vars": self._map_output_vars(action, ctx),
                "retry": action["exec"]["retry"],
                "timeout_ms": action["exec"]["timeout_ms"],
                "rate_limit": action["exec"]["rate_limit"]
            }
            
            node = {
                "id": nid,
                "type": "action",
                "data": node_data,
                "label": self._ui_label("Action", action),
                "icon": self._icon_for(action, ctx)
            }
            
            G["nodes"].append(node)
            self.index["actionMap"][action["local_id"]] = nid
    
    def _lower_flow_control(self, G: Dict[str, Any], executable_doc: Dict[str, Any], ctx: Dict[str, Any]):
        """Lower flow control constructs into graph nodes"""
        flow_control = executable_doc.get("flow_control", {})
        
        # Handle IF/ELSE conditions
        self._lower_conditions(G, flow_control.get("conditions", []))
        
        # Handle parallel execution
        self._lower_parallel_execution(G, flow_control.get("parallel_execution", []))
        
        # Handle loops
        self._lower_loops(G, flow_control.get("loops", []))
    
    def _lower_conditions(self, G: Dict[str, Any], conditions: List[Dict[str, Any]]):
        """Lower IF/ELSE conditions to gateway_if nodes"""
        for conditional in conditions:
            gid = self._new_node_id("g")
            
            # Process branches
            branches = []
            for branch in conditional.get("branches", []):
                branch_data = {
                    "name": branch.get("name") or self._auto_name("branch"),
                    "expr": self._to_expr_ast(branch.get("expr")),
                    "to": self._target_node_id(branch.get("target_ref"), self.index)
                }
                branches.append(branch_data)
            
            # Handle else branch
            else_to = None
            if conditional.get("else_ref"):
                else_to = self._target_node_id(conditional["else_ref"], self.index)
            
            # Create gateway node
            node = {
                "id": gid,
                "type": "gateway_if",
                "data": {
                    "branches": branches,
                    "else_to": else_to
                },
                "label": "IF"
            }
            
            G["nodes"].append(node)
            self.index["gatewayMap"][conditional.get("local_id", gid)] = gid
            
            # Wire incoming edges to this gateway
            self._wire_incoming(gid, conditional.get("incoming_ref"), self.index, G)
    
    def _lower_parallel_execution(self, G: Dict[str, Any], parallel_execs: List[Dict[str, Any]]):
        """Lower parallel execution to parallel + join nodes"""
        for p in parallel_execs:
            pid = self._new_node_id("par")
            jid = self._new_node_id("join")
            
            # Create parallel node
            parallel_node = {
                "id": pid,
                "type": "parallel",
                "label": "Fan-out"
            }
            G["nodes"].append(parallel_node)
            
            # Create join node
            join_node = {
                "id": jid,
                "type": "join",
                "data": {"mode": "all"},
                "label": "Join (ALL)"
            }
            G["nodes"].append(join_node)
            
            # Connect parallel to targets
            for branch_ref in p.get("targets", []):
                target_id = self._target_node_id(branch_ref, self.index)
                if target_id:
                    edge = {
                        "id": f"e_{pid}_{target_id}",
                        "source": pid,
                        "target": target_id,
                        "label": "parallel_branch"
                    }
                    G["edges"].append(edge)
                    
                    # Ensure each branch ultimately connects to join
                    self._ensure_path_terminates_at_join(G, branch_ref, jid, self.index)
            
            # Connect incoming to parallel
            self._connect_into(G, pid, p.get("incoming_ref"), self.index)
            
            # Connect join to outgoing
            self._connect_out(G, jid, p.get("outgoing_ref"), self.index)
    
    def _lower_loops(self, G: Dict[str, Any], loops: List[Dict[str, Any]]):
        """Lower loop constructs to loop nodes"""
        for lp in loops:
            lid = self._new_node_id("loop")
            
            if lp.get("kind") == "while":
                node_data = {
                    "condition": self._to_expr_ast(lp.get("condition")),
                    "body_start": self._target_node_id(lp.get("body_ref"), self.index),
                    "max_iterations": lp.get("max_iterations", 1000)
                }
                
                node = {
                    "id": lid,
                    "type": "loop_while",
                    "data": node_data,
                    "label": "While"
                }
                
            elif lp.get("kind") == "foreach":
                node_data = {
                    "source_array_expr": self._to_expr_ast(lp.get("source")),
                    "item_var": lp.get("item_var"),
                    "index_var": lp.get("index_var"),
                    "body_start": self._target_node_id(lp.get("body_ref"), self.index),
                    "max_concurrency": lp.get("max_concurrency", 5)
                }
                
                node = {
                    "id": lid,
                    "type": "loop_foreach",
                    "data": node_data,
                    "label": "ForEach"
                }
            
            G["nodes"].append(node)
            self.index["loopMap"][lp.get("local_id", lid)] = lid
            
            # Connect incoming to loop
            self._connect_into(G, lid, lp.get("incoming_ref"), self.index)
    
    def _add_routed_edges(self, G: Dict[str, Any], executable_doc: Dict[str, Any]):
        """Add linear/routed edges between nodes"""
        routes = executable_doc.get("routes", [])
        
        for route in routes:
            source_id = self._target_node_id(route.get("from_ref"), self.index)
            target_id = self._target_node_id(route.get("to_ref"), self.index)
            
            if source_id and target_id:
                edge = {
                    "id": f"e_{source_id}_{target_id}",
                    "source": source_id,
                    "target": target_id,
                    "when": route.get("when", "success"),
                    "condition": self._to_expr_ast(route.get("expr")) if route.get("expr") else None,
                    "label": route.get("label", "")
                }
                G["edges"].append(edge)
            else:
                if not source_id:
                    self.report.add_error(
                        "MISSING_SOURCE_REF",
                        f"routes.{route.get('from_ref')}",
                        f"Source reference '{route.get('from_ref')}' not found"
                    )
                if not target_id:
                    self.report.add_error(
                        "MISSING_TARGET_REF",
                        f"routes.{route.get('to_ref')}",
                        f"Target reference '{route.get('to_ref')}' not found"
                    )
    
    def _compute_globals_and_ui(self, G: Dict[str, Any], executable_doc: Dict[str, Any], ctx: Dict[str, Any]):
        """Compute global settings and UI layout"""
        # Set global policies
        G["globals"] = self._choose_globals(executable_doc, ctx)
        
        # Apply layout
        layout_opts = ctx.get("layout", "dagre")
        self._apply_layout(G, layout_opts)
    
    def _choose_globals(self, executable_doc: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Choose global settings for the workflow"""
        globals_config = {}
        
        # Get policies from executable
        policies = executable_doc.get("policies", {})
        
        if "retry" in policies:
            globals_config["retry"] = policies["retry"]
        
        if "timeout_ms" in policies:
            globals_config["timeout_ms"] = policies["timeout_ms"]
        
        if "rate_limit" in policies:
            globals_config["rate_limit"] = policies["rate_limit"]
        
        # Set defaults
        if "max_parallelism" not in globals_config:
            globals_config["max_parallelism"] = 10
        
        return globals_config
    
    def _apply_layout(self, G: Dict[str, Any], layout: str):
        """Apply layout algorithm to the graph"""
        G["ui"]["layout"] = layout
        
        # In a real implementation, you'd use dagre/ELK to compute positions
        # For now, just set some basic positioning
        for i, node in enumerate(G["nodes"]):
            if "position" not in node:
                node["position"] = {"x": i * 200, "y": i * 100}
    
    def _validate_dag(self, G: Dict[str, Any]) -> bool:
        """Validate the final DAG document"""
        # Check that all nodes have required fields
        for node in G.get("nodes", []):
            if not self._validate_required_fields(node, ["id", "type"], "nodes"):
                return False
        
        # Check that all edges have required fields
        for edge in G.get("edges", []):
            if not self._validate_required_fields(edge, ["id", "source", "target"], "edges"):
                return False
        
        # Check for orphaned nodes (nodes with no incoming or outgoing edges)
        orphaned = self._find_orphaned_nodes(G)
        if orphaned:
            for node_id in orphaned:
                self.report.add_warning(
                    "ORPHANED_NODE",
                    f"nodes.{node_id}",
                    f"Node {node_id} has no connections"
                )
        
        return True
    
    def _find_orphaned_nodes(self, G: Dict[str, Any]) -> List[str]:
        """Find nodes with no connections"""
        connected_nodes = set()
        
        for edge in G.get("edges", []):
            connected_nodes.add(edge["source"])
            connected_nodes.add(edge["target"])
        
        all_nodes = {node["id"] for node in G.get("nodes", [])}
        return list(all_nodes - connected_nodes)
    
    def _new_node_id(self, prefix: str) -> str:
        """Generate a new node ID"""
        self.node_counter[prefix] += 1
        return f"{prefix}{self.node_counter[prefix]}"
    
    def _target_node_id(self, ref: str, index: Dict[str, Any]) -> Optional[str]:
        """Get the target node ID from a reference"""
        # Check all index maps
        for map_name, mapping in index.items():
            if ref in mapping:
                return mapping[ref]
        
        # If not found, the reference might be invalid
        self.report.add_warning(
            "UNRESOLVED_REF",
            "",
            f"Reference '{ref}' could not be resolved to a node"
        )
        return None
    
    def _wire_incoming(self, node_id: str, incoming_ref: str, index: Dict[str, Any], G: Dict[str, Any]):
        """Wire incoming edges to a node"""
        if not incoming_ref:
            return
        
        # Find the source node and create an edge
        source_id = self._target_node_id(incoming_ref, index)
        if source_id:
            edge = {
                "id": f"e_{source_id}_{node_id}",
                "source": source_id,
                "target": node_id,
                "label": "flow"
            }
            G["edges"].append(edge)
    
    def _connect_into(self, G: Dict[str, Any], node_id: str, incoming_ref: str, index: Dict[str, Any]):
        """Connect a node to its incoming reference"""
        self._wire_incoming(node_id, incoming_ref, index, G)
    
    def _connect_out(self, G: Dict[str, Any], node_id: str, outgoing_ref: str, index: Dict[str, Any]):
        """Connect a node to its outgoing reference"""
        if not outgoing_ref:
            return
        
        # Find the target node and create an edge
        target_id = self._target_node_id(outgoing_ref, index)
        if target_id:
            edge = {
                "id": f"e_{node_id}_{target_id}",
                "source": node_id,
                "target": target_id,
                "label": "flow"
            }
            G["edges"].append(edge)
    
    def _ensure_path_terminates_at_join(self, G: Dict[str, Any], branch_ref: str, join_id: str, index: Dict[str, Any]):
        """Ensure a branch path terminates at a join node"""
        # This is a simplified implementation
        # In a real implementation, you'd trace the path and ensure it reaches the join
        pass
    
    def _to_expr_ast(self, expr: Any) -> Any:
        """Convert expression to AST format"""
        # This is a placeholder - in a real implementation you'd parse expressions
        # For now, just return the expression as-is
        return expr
    
    def _ui_label(self, node_type: str, item: Dict[str, Any]) -> str:
        """Generate UI label for a node"""
        if "label" in item:
            return item["label"]
        
        # Generate default label
        if node_type == "Trigger":
            return f"Trigger: {item.get('exec', {}).get('provider', 'Unknown')}"
        elif node_type == "Action":
            return f"Action: {item.get('exec', {}).get('action_slug', 'Unknown')}"
        else:
            return node_type
    
    def _icon_for(self, item: Dict[str, Any], ctx: Dict[str, Any]) -> Optional[str]:
        """Get icon for a node"""
        # This would map to actual icon assets
        # For now, return None
        return None
    
    def _build_input_template(self, action: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Build input template for an action"""
        # This would build a template based on the action's parameter specification
        # For now, return a basic structure
        return {
            "required": action.get("exec", {}).get("required_inputs", {}),
            "optional": action.get("exec", {}).get("optional_inputs", {})
        }
    
    def _map_output_vars(self, action: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, str]:
        """Map output variables for an action"""
        # This would map the action's outputs to variable names
        # For now, return a basic mapping
        return {
            "result": "$.result",
            "status": "$.status"
        }
    
    def _auto_name(self, prefix: str) -> str:
        """Generate an automatic name"""
        return f"{prefix}_{len(self.index.get('gatewayMap', {})) + 1}"
