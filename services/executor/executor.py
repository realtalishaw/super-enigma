"""
Workflow Execution Engine - Microservice

A language-agnostic, single-process orchestrator that executes DAG workflows
using Composio for tool execution. Supports idempotency, retries, conditional
logic, parallel execution, joins, and loops.

This module can be imported and used from:
- API endpoints
- CLI tools
- Scripts
- Other services
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Union
from dataclasses import dataclass, field
from enum import Enum
import httpx
from jinja2 import Template, Environment, BaseLoader

from core.logging_config import get_logger

logger = get_logger(__name__)

class NodeType(str, Enum):
    """Supported node types in the DAG"""
    TRIGGER = "trigger"
    ACTION = "action"
    GATEWAY_IF = "gateway_if"
    GATEWAY_SWITCH = "gateway_switch"
    PARALLEL = "parallel"
    JOIN = "join"
    LOOP_WHILE = "loop_while"
    LOOP_FOREACH = "loop_foreach"

class NodeStatus(str, Enum):
    """Node execution status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"

class RunStatus(str, Enum):
    """Workflow run status"""
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

@dataclass
class ExecutionContext:
    """Context for workflow execution"""
    inputs: Dict[str, Any] = field(default_factory=dict)
    vars: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    last_node_id: Optional[str] = None
    user_id: Optional[str] = None

@dataclass
class NodeExecution:
    """Represents a node execution within a run"""
    run_id: str
    node_id: str
    status: NodeStatus
    attempt: int = 0
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    from_cache: bool = False

@dataclass
class WorkflowRun:
    """Represents a workflow execution run"""
    run_id: str
    workflow_id: str
    version: str
    user_id: str
    status: RunStatus
    started_at: datetime
    finished_at: Optional[datetime] = None
    trigger_digest: Optional[str] = None

class ComposioClient:
    """Client for interacting with Composio API"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=60.0
        )
    
    async def execute_action(self, tool: str, action: str, connection_id: str, 
                           arguments: Dict[str, Any], timeout_ms: int = 45000, 
                           user_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute a Composio action using direct v3 REST API calls"""
        try:
            # Compose the v3 endpoint using the action slug (keep it upper-case)
            tool_slug = action.upper()
            url = f"{self.base_url}/api/v3/tools/execute/{tool_slug}"

            payload = {
                "connected_account_id": connection_id,
                "arguments": arguments,
            }

            # Use x-api-key header per v3 docs
            headers = {"x-api-key": self.api_key}

            logger.info(f"Executing Composio action: {action}")
            logger.info(f"Connection ID: {connection_id}")
            logger.info(f"Arguments: {arguments}")
            logger.info(f"URL: {url}")

            response = await self.client.post(
                url,
                json=payload,
                headers=headers,
                timeout=timeout_ms / 1000.0,
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Composio action execution result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Composio action execution failed: {action}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

class StateStore:
    """In-memory state store (replace with database in production)"""
    
    def __init__(self):
        self.runs: Dict[str, WorkflowRun] = {}
        self.node_executions: Dict[str, List[NodeExecution]] = {}
        self.joins: Dict[str, Set[str]] = {}
    
    def persist_run(self, run: WorkflowRun):
        """Persist a workflow run"""
        self.runs[run.run_id] = run
    
    def get_run(self, run_id: str) -> Optional[WorkflowRun]:
        """Get a workflow run by ID"""
        return self.runs.get(run_id)
    
    def update_run_status(self, run_id: str, status: RunStatus, finished_at: Optional[datetime] = None):
        """Update run status"""
        if run_id in self.runs:
            self.runs[run_id].status = status
            if finished_at:
                self.runs[run_id].finished_at = finished_at
    
    def record_node_execution(self, execution: NodeExecution):
        """Record a node execution"""
        if execution.run_id not in self.node_executions:
            self.node_executions[execution.run_id] = []
        self.node_executions[execution.run_id].append(execution)
    
    def get_node_executions(self, run_id: str) -> List[NodeExecution]:
        """Get all node executions for a run"""
        return self.node_executions.get(run_id, [])
    
    def record_join_arrival(self, run_id: str, node_id: str, source_node_id: str):
        """Record arrival at a join node"""
        key = f"{run_id}:{node_id}"
        if key not in self.joins:
            self.joins[key] = set()
        self.joins[key].add(source_node_id)
        return len(self.joins[key])

class IdempotencyCache:
    """In-memory idempotency cache (replace with Redis in production)"""
    
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttls: Dict[str, datetime] = {}
    
    def has(self, key: str) -> bool:
        """Check if key exists and is not expired"""
        if key not in self.cache:
            return False
        if datetime.now() > self.ttls.get(key, datetime.min):
            del self.cache[key]
            del self.ttls[key]
            return False
        return True
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from cache"""
        if self.has(key):
            return self.cache[key]
        return None
    
    def put(self, key: str, value: Dict[str, Any], ttl_hours: int = 24):
        """Put value in cache with TTL"""
        self.cache[key] = value
        self.ttls[key] = datetime.now() + timedelta(hours=ttl_hours)

class WorkflowExecutor:
    """Main workflow execution engine"""
    
    def __init__(self, composio_client: ComposioClient, state_store: StateStore, 
                 idempotency_cache: IdempotencyCache):
        self.composio = composio_client
        self.state_store = state_store
        self.idempotency_cache = idempotency_cache
        self.jinja_env = Environment(loader=BaseLoader())
        
        # Add custom filters for email parsing
        def extract_email(value):
            """Extract email address from 'Name <email>' format or return as-is"""
            if not value:
                return value
            # Handle "Name <email@domain.com>" format
            if '<' in value and '>' in value:
                start = value.find('<') + 1
                end = value.find('>')
                if start < end:
                    return value[start:end]
            # Return as-is if no angle brackets found
            return value
        
        self.jinja_env.filters['extract_email'] = extract_email
        
        # Default settings
        self.defaults = {
            "retry": {"retries": 1, "backoff": "linear", "delay_ms": 1000},
            "timeout": 45000
        }
    
    async def execute_workflow(self, dag: Dict[str, Any], event_payload: Dict[str, Any], 
                             user_id: str, workflow_id: str, version: str = "1.0") -> str:
        """
        Execute a workflow DAG
        
        Args:
            dag: DAG JSON conforming to schema
            event_payload: Event data from trigger
            user_id: User executing the workflow
            workflow_id: ID of the workflow
            version: Version of the workflow
            
        Returns:
            run_id: Unique identifier for this execution
        """
        try:
            # Step 0: Boot
            logger.info(f"Starting workflow execution for {workflow_id}")
            
            # Step 1: Preflight validation
            self._validate_dag(dag)
            
            # Step 2: Trigger registration (would be done at workflow creation time)
            # self._register_triggers(dag)
            
            # Step 3: Activation
            run_id = str(uuid.uuid4())
            logger.info(f"Initializing execution context with event payload: {event_payload}")
            context = ExecutionContext(
                inputs=event_payload,
                vars={},
                artifacts={},
                errors={},
                user_id=user_id
            )
            
            run = WorkflowRun(
                run_id=run_id,
                workflow_id=workflow_id,
                version=version,
                user_id=user_id,
                status=RunStatus.RUNNING,
                started_at=datetime.now()
            )
            self.state_store.persist_run(run)
            
            # Find trigger nodes and queue their successors
            ready = []
            for node in dag["nodes"]:
                if node["type"] == NodeType.TRIGGER:
                    for edge in dag["edges"]:
                        if edge["source"] == node["id"]:
                            ready.append(edge["target"])
            
            # Step 4: Orchestrate
            await self._orchestrate(run_id, context, ready, dag)
            
            # Step 8: Finalize
            self._finalize_run_status(run_id)
            
            logger.info(f"Workflow execution completed: {run_id}")
            return run_id
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise
    
    def _validate_dag(self, dag: Dict[str, Any]):
        """Validate DAG structure"""
        if not dag.get("nodes"):
            raise ValueError("DAG must have nodes")
        
        if not dag.get("edges"):
            raise ValueError("DAG must have edges")
        
        # Validate edges reference existing nodes
        node_ids = {node["id"] for node in dag["nodes"]}
        for edge in dag["edges"]:
            if edge["source"] not in node_ids:
                raise ValueError(f"Edge source {edge['source']} not found in nodes")
            if edge["target"] not in node_ids:
                raise ValueError(f"Edge target {edge['target']} not found in nodes")
        
        # Validate action nodes
        for node in dag["nodes"]:
            if node["type"] == NodeType.ACTION:
                if not node["data"].get("tool"):
                    raise ValueError(f"Action node {node['id']} missing tool")
                if not node["data"].get("action"):
                    raise ValueError(f"Action node {node['id']} missing action")
                if node["data"].get("requires_auth", True) and not node["data"].get("connection_id"):
                    raise ValueError(f"Action node {node['id']} requires connection_id")
    
    async def _orchestrate(self, run_id: str, context: ExecutionContext, 
                          ready: List[str], dag: Dict[str, Any]):
        """Main orchestration loop"""
        while ready:
            node_id = ready.pop(0)
            
            # Check if node already executed
            if self._node_already_final(run_id, node_id):
                continue
            
            node = self._get_node(node_id, dag)
            if not node:
                continue
            
            try:
                await self._execute_node(run_id, node, context, dag)
                self._route_successors(run_id, node_id, context, ready, dag)
            except Exception as e:
                logger.error(f"Node {node_id} execution failed: {e}")
                self._mark_error(run_id, node_id, str(e))
    
    async def _execute_node(self, run_id: str, node: Dict[str, Any], 
                           context: ExecutionContext, dag: Dict[str, Any]):
        """Execute a single node"""
        node_type = node["type"]
        
        if node_type == NodeType.ACTION:
            await self._exec_action(run_id, node, context)
        elif node_type == NodeType.GATEWAY_IF:
            self._exec_gateway_if(run_id, node, context, dag)
        elif node_type == NodeType.GATEWAY_SWITCH:
            self._exec_gateway_switch(run_id, node, context, dag)
        elif node_type == NodeType.PARALLEL:
            self._exec_parallel(run_id, node, context, dag)
        elif node_type == NodeType.JOIN:
            self._exec_join(run_id, node, context, dag)
        elif node_type == NodeType.LOOP_WHILE:
            self._exec_loop_while(run_id, node, context, dag)
        elif node_type == NodeType.LOOP_FOREACH:
            self._exec_loop_foreach(run_id, node, context, dag)
        elif node_type == NodeType.TRIGGER:
            self._mark_skipped(run_id, node["id"])
    
    async def _exec_action(self, run_id: str, node: Dict[str, Any], context: ExecutionContext):
        """Execute an action node"""
        retry_config = node["data"].get("retry", self.defaults["retry"])
        timeout = node["data"].get("timeout_ms", self.defaults["timeout"])
        
        # Construct idempotency key
        input_digest = hashlib.md5(
            json.dumps(node["data"].get("input_template", {}), sort_keys=True).encode()
        ).hexdigest()
        idem_key = f"{run_id}:{node['id']}:{input_digest}"
        
        # Check cache
        if self.idempotency_cache.has(idem_key):
            cached = self.idempotency_cache.get(idem_key)
            self._mark_done(run_id, node["id"], cached, from_cache=True)
            return
        
        # Render template
        logger.info(f"Rendering template for node {node['id']}: {node['data'].get('input_template', {})}")
        logger.info(f"Context inputs: {context.inputs}")
        args = self._render_template(node["data"].get("input_template", {}), context)
        logger.info(f"Rendered arguments: {args}")
        
        # Execute with retries
        attempt = 0
        while attempt <= retry_config["retries"]:
            attempt += 1
            try:
                logger.info(f"Executing Composio action: {node['data']['tool']}.{node['data']['action']}")
                logger.info(f"Connection ID: {node['data']['connection_id']}")
                logger.info(f"Arguments: {args}")
                result = await self.composio.execute_action(
                    tool=node["data"]["tool"],
                    action=node["data"]["action"],
                    connection_id=node["data"]["connection_id"],
                    arguments=args,
                    timeout_ms=timeout,
                    user_id=context.user_id
                )
                
                # Update context
                self._update_context_from_result(context, node, result)
                
                # Cache result
                slim_result = self._slim_result(result)
                self.idempotency_cache.put(idem_key, slim_result)
                
                self._mark_done(run_id, node["id"], slim_result)
                return
                
            except Exception as e:
                if attempt > retry_config["retries"]:
                    self._mark_error(run_id, node["id"], f"Retries exhausted: {e}")
                    return
                
                # Wait before retry
                delay = retry_config["delay_ms"] * attempt if retry_config["backoff"] == "linear" else retry_config["delay_ms"] * (2 ** (attempt - 1))
                await asyncio.sleep(delay / 1000)
    
    def _exec_gateway_if(self, run_id: str, node: Dict[str, Any], 
                         context: ExecutionContext, dag: Dict[str, Any]):
        """Execute an IF gateway node"""
        target = None
        for branch in node["data"].get("branches", []):
            if self._eval_expr(branch["expr"], context):
                target = branch["to"]
                break
        
        output = {"branch": target or "else"}
        self._mark_done(run_id, node["id"], output)
        
        # Queue next node
        if target:
            # This would be handled by route_successors
            pass
        elif node["data"].get("else_to"):
            # This would be handled by route_successors
            pass
    
    def _exec_gateway_switch(self, run_id: str, node: Dict[str, Any], 
                            context: ExecutionContext, dag: Dict[str, Any]):
        """Execute a SWITCH gateway node"""
        key = self._eval_value(node["data"]["selector"], context)
        target = None
        
        for case in node["data"].get("cases", []):
            if case["value"] == key:
                target = case["to"]
                break
        
        if not target and node["data"].get("default_to"):
            target = node["data"]["default_to"]
        
        output = {"case": key}
        self._mark_done(run_id, node["id"], output)
    
    def _exec_parallel(self, run_id: str, node: Dict[str, Any], 
                      context: ExecutionContext, dag: Dict[str, Any]):
        """Execute a parallel node"""
        self._mark_done(run_id, node["id"], {"fanout": True})
        # Successors will be handled by route_successors
    
    def _exec_join(self, run_id: str, node: Dict[str, Any], 
                   context: ExecutionContext, dag: Dict[str, Any]):
        """Execute a join node"""
        arrived = self.state_store.record_join_arrival(run_id, node["id"], context.last_node_id)
        
        if self._join_ready(node, arrived, dag):
            self._mark_done(run_id, node["id"], {"arrived": arrived})
        else:
            # Wait for more arrivals
            pass
    
    def _exec_loop_while(self, run_id: str, node: Dict[str, Any], 
                        context: ExecutionContext, dag: Dict[str, Any]):
        """Execute a WHILE loop node"""
        if self._eval_expr(node["data"]["condition"], context):
            # Continue loop
            # This would increment counter and queue body_start
            pass
        else:
            self._mark_done(run_id, node["id"], {"loop": "exited"})
    
    def _exec_loop_foreach(self, run_id: str, node: Dict[str, Any], 
                          context: ExecutionContext, dag: Dict[str, Any]):
        """Execute a FOREACH loop node"""
        items = self._eval_value(node["data"]["source_array_expr"], context)
        if not isinstance(items, list):
            raise ValueError("FOREACH source must be a list")
        
        n = len(items)
        self._mark_progress(run_id, node["id"], {"spawned": n})
        
        # This would spawn shards for parallel execution
        # For now, just mark as done
        self._mark_done(run_id, node["id"], {"spawned": n})
    
    def _route_successors(self, run_id: str, node_id: str, context: ExecutionContext, 
                         ready: List[str], dag: Dict[str, Any]):
        """Route to successor nodes"""
        status = self._get_node_status(run_id, node_id)
        
        for edge in dag["edges"]:
            if edge["source"] == node_id:
                when_ok = (
                    edge.get("when") is None or
                    edge.get("when") == "always" or
                    (edge.get("when") == "success" and status == NodeStatus.DONE) or
                    (edge.get("when") == "error" and status == NodeStatus.ERROR)
                )
                
                if when_ok and self._edge_condition_true(edge, context):
                    ready.append(edge["target"])
    
    def _mark_done(self, run_id: str, node_id: str, output: Dict[str, Any], from_cache: bool = False):
        """Mark a node as successfully completed"""
        execution = NodeExecution(
            run_id=run_id,
            node_id=node_id,
            status=NodeStatus.DONE,
            output=output,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            from_cache=from_cache
        )
        self.state_store.record_node_execution(execution)
    
    def _mark_error(self, run_id: str, node_id: str, error: str):
        """Mark a node as failed"""
        execution = NodeExecution(
            run_id=run_id,
            node_id=node_id,
            status=NodeStatus.ERROR,
            error=error,
            started_at=datetime.now(),
            finished_at=datetime.now()
        )
        self.state_store.record_node_execution(execution)
    
    def _mark_skipped(self, run_id: str, node_id: str):
        """Mark a node as skipped"""
        execution = NodeExecution(
            run_id=run_id,
            node_id=node_id,
            status=NodeStatus.SKIPPED,
            started_at=datetime.now(),
            finished_at=datetime.now()
        )
        self.state_store.record_node_execution(execution)
    
    def _mark_progress(self, run_id: str, node_id: str, progress: Dict[str, Any]):
        """Mark progress on a node"""
        execution = NodeExecution(
            run_id=run_id,
            node_id=node_id,
            status=NodeStatus.RUNNING,
            output=progress,
            started_at=datetime.now()
        )
        self.state_store.record_node_execution(execution)
    
    def _finalize_run_status(self, run_id: str):
        """Finalize the run status"""
        executions = self.state_store.get_node_executions(run_id)
        
        if any(execution.status == NodeStatus.ERROR for execution in executions):
            self.state_store.update_run_status(run_id, RunStatus.FAILED, datetime.now())
        else:
            self.state_store.update_run_status(run_id, RunStatus.SUCCESS, datetime.now())
    
    # Helper methods
    def _node_already_final(self, run_id: str, node_id: str) -> bool:
        """Check if node has already reached final state"""
        executions = self.state_store.get_node_executions(run_id)
        for execution in executions:
            if execution.node_id == node_id and execution.status in [NodeStatus.DONE, NodeStatus.ERROR, NodeStatus.SKIPPED]:
                return True
        return False
    
    def _get_node(self, node_id: str, dag: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get a node by ID from the DAG"""
        for node in dag["nodes"]:
            if node["id"] == node_id:
                return node
        return None
    
    def _get_node_status(self, run_id: str, node_id: str) -> Optional[NodeStatus]:
        """Get the status of a node execution"""
        executions = self.state_store.get_node_executions(run_id)
        for execution in executions:
            if execution.node_id == node_id:
                return execution.status
        return None
    
    def _edge_condition_true(self, edge: Dict[str, Any], context: ExecutionContext) -> bool:
        """Check if an edge condition is true"""
        if "condition" not in edge:
            return True
        return self._eval_condition(edge["condition"], context)
    
    def _join_ready(self, node: Dict[str, Any], arrived_count: int, dag: Dict[str, Any]) -> bool:
        """Check if a join node is ready to proceed"""
        mode = node["data"].get("mode", "all")
        incoming_count = len([e for e in dag["edges"] if e["target"] == node["id"]])
        
        if mode == "all":
            return arrived_count == incoming_count
        elif mode == "any":
            return arrived_count >= 1
        elif mode == "quorum":
            count = node["data"].get("count", 2)
            return arrived_count >= count
        return False
    
    def _render_template(self, template: Union[str, Dict[str, Any]], context: ExecutionContext) -> Any:
        """Render a Jinja2 template with context - only when placeholders are present"""
        logger.info(f"Rendering template: {template}")
        context_dict = self._context_to_dict(context)
        logger.info(f"Context dictionary: {context_dict}")
        
        if isinstance(template, str):
            # Only render if the string contains template placeholders
            if "{{" in template and "}}" in template:
                jinja_template = self.jinja_env.from_string(template)
                result = jinja_template.render(**context_dict)
                logger.info(f"Rendered string template: '{template}' -> '{result}'")
                return result
            else:
                # No placeholders, return as-is
                logger.info(f"No placeholders found, returning string as-is: '{template}'")
                return template
        elif isinstance(template, dict):
            # For dict templates, only render string values that contain placeholders
            result = {}
            for key, value in template.items():
                if isinstance(value, str):
                    if "{{" in value and "}}" in value:
                        # Has placeholders, render it
                        jinja_template = self.jinja_env.from_string(value)
                        rendered_value = jinja_template.render(**context_dict)
                        logger.info(f"Rendered template for {key}: '{value}' -> '{rendered_value}'")
                        result[key] = rendered_value
                    else:
                        # No placeholders, use as-is
                        logger.info(f"No placeholders for {key}, using value as-is: '{value}'")
                        result[key] = value
                else:
                    result[key] = value
            logger.info(f"Final rendered dict template: {result}")
            return result
        return template
    
    def _context_to_dict(self, context: ExecutionContext) -> Dict[str, Any]:
        """Convert context to a flat dictionary for template rendering"""
        result = {}
        # Add inputs at the root level so templates can access inputs.sender, inputs.subject, etc.
        result["inputs"] = context.inputs
        result.update(context.vars)
        result.update(context.artifacts)
        return result
    
    def _eval_expr(self, expr: str, context: ExecutionContext) -> bool:
        """Evaluate a simple expression (placeholder implementation)"""
        # This is a simplified implementation - in production you'd want a proper expression evaluator
        try:
            # Simple variable substitution for now
            context_dict = self._context_to_dict(context)
            return bool(eval(expr, {"__builtins__": {}}, context_dict))
        except:
            return False
    
    def _eval_value(self, expr: str, context: ExecutionContext) -> Any:
        """Evaluate a value expression (placeholder implementation)"""
        try:
            context_dict = self._context_to_dict(context)
            return eval(expr, {"__builtins__": {}}, context_dict)
        except:
            return None
    
    def _eval_condition(self, condition: Dict[str, Any], context: ExecutionContext) -> bool:
        """Evaluate a condition (placeholder implementation)"""
        # This would implement the full condition evaluation logic from the schema
        # For now, return True as a placeholder
        return True
    
    def _update_context_from_result(self, context: ExecutionContext, node: Dict[str, Any], result: Dict[str, Any]):
        """Update context with action result"""
        if "output_vars" in node["data"]:
            for var_name, path in node["data"]["output_vars"].items():
                # Simple path extraction for now
                if path in result:
                    context.vars[var_name] = result[path]
    
    def _slim_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Create a slim version of result for caching"""
        # Remove large fields, keep essential data
        slim = {}
        for key, value in result.items():
            if isinstance(value, (str, int, float, bool)) or (isinstance(value, list) and len(value) < 10):
                slim[key] = value
            elif isinstance(value, dict) and len(str(value)) < 1000:
                slim[key] = value
        return slim

# Factory function for easy instantiation
def create_executor(composio_base_url: str, composio_api_key: str) -> WorkflowExecutor:
    """Create a workflow executor instance"""
    composio_client = ComposioClient(composio_base_url, composio_api_key)
    state_store = StateStore()
    idempotency_cache = IdempotencyCache()
    
    return WorkflowExecutor(composio_client, state_store, idempotency_cache)

# Async execution function for easy calling from anywhere
async def execute_workflow_async(dag: Dict[str, Any], event_payload: Dict[str, Any],
                                user_id: str, workflow_id: str, version: str = "1.0",
                                composio_base_url: str = None, composio_api_key: str = None) -> str:
    """
    Async function to execute a workflow - can be called from anywhere in the project
    
    Args:
        dag: DAG JSON conforming to schema
        event_payload: Event data from trigger
        user_id: User executing the workflow
        workflow_id: ID of the workflow
        version: Version of the workflow
        composio_base_url: Composio API base URL
        composio_api_key: Composio API key
        
    Returns:
        run_id: Unique identifier for this execution
    """
    if not composio_base_url or not composio_api_key:
        raise ValueError("Composio base URL and API key are required")
    
    executor = create_executor(composio_base_url, composio_api_key)
    return await executor.execute_workflow(dag, event_payload, user_id, workflow_id, version)

# Sync wrapper for non-async contexts
def execute_workflow_sync(dag: Dict[str, Any], event_payload: Dict[str, Any],
                         user_id: str, workflow_id: str, version: str = "1.0",
                         composio_base_url: str = None, composio_api_key: str = None) -> str:
    """
    Sync function to execute a workflow - can be called from anywhere in the project
    
    Args:
        dag: DAG JSON conforming to schema
        event_payload: Event data from trigger
        user_id: User executing the workflow
        workflow_id: ID of the workflow
        version: Version of the workflow
        composio_base_url: Composio API base URL
        composio_api_key: Composio API key
        
    Returns:
        run_id: Unique identifier for this execution
    """
    return asyncio.run(execute_workflow_async(
        dag, event_payload, user_id, workflow_id, version, composio_base_url, composio_api_key
    ))
    
    
    