"""
Template Materializer (T→E)

Converts a high-level Template JSON with placeholders into a fully-resolved 
Executable JSON by filling placeholders, choosing concrete provider actions/triggers, 
resolving connections/secrets, normalizing params, and attaching operational policy.
"""

import copy
import logging
from typing import Dict, Any, List, Optional, Tuple
from base import BaseCompiler, CompilerReport

logger = logging.getLogger(__name__)


class TemplateMaterializer(BaseCompiler):
    """
    Template Materializer: Template JSON → Executable JSON
    
    Hydrates intent into something runnable by:
    - Filling placeholders
    - Choosing concrete provider actions/triggers
    - Resolving connections/secrets
    - Normalizing params
    - Attaching operational policy (retries, timeouts, rate limits)
    """
    
    def compile(self, template_doc: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main compilation method for Template → Executable
        
        Args:
            template_doc: Template JSON document
            ctx: Context containing catalog, user, connections, answers, defaults
            
        Returns:
            Dict with executable_doc and report
        """
        self.report = CompilerReport()
        
        try:
            # 1) Validate template
            if not self._validate_template(template_doc):
                return {"executable_doc": None, "report": self.report}
            
            # 2) Fill missing information
            filled = self._apply_answers(template_doc, ctx.get("answers", {}))
            
            # 3) Resolve providers/actions/triggers
            self._resolve_triggers(filled, ctx)
            self._resolve_actions(filled, ctx)
            
            # 4) Policies & security
            self._inject_default_policies(filled, ctx.get("defaults", {}))
            self._reject_plaintext_secrets(filled, ctx.get("connections", {}))
            
            # 5) Lint and auto-repair where safe
            patched, repairs = self._attempt_repair(filled, ctx)
            self.report.repairs.extend(repairs)
            
            # 6) Final validation
            if not self._validate_executable(patched):
                return {"executable_doc": None, "report": self.report}
            
            return {
                "executable_doc": patched,
                "report": self.report
            }
            
        except Exception as e:
            logger.error(f"Template materialization failed: {e}")
            self.report.add_error(
                "INTERNAL_ERROR",
                "",
                f"Internal error during materialization: {str(e)}"
            )
            return {"executable_doc": None, "report": self.report}
    
    def _validate_template(self, template_doc: Dict[str, Any]) -> bool:
        """Validate template document structure"""
        required_fields = ["workflow_id", "version", "triggers", "actions"]
        
        if not self._validate_required_fields(template_doc, required_fields):
            return False
        
        # Validate triggers
        for i, trigger in enumerate(template_doc.get("triggers", [])):
            if not self._validate_required_fields(trigger, ["local_id"], f"triggers[{i}]"):
                return False
        
        # Validate actions
        for i, action in enumerate(template_doc.get("actions", [])):
            if not self._validate_required_fields(action, ["local_id"], f"actions[{i}]"):
                return False
        
        return True
    
    def _apply_answers(self, template_doc: Dict[str, Any], answers: Dict[str, Any]) -> Dict[str, Any]:
        """Apply user answers to fill placeholders"""
        filled = copy.deepcopy(template_doc)
        
        # Fill placeholders in the entire document
        self._fill_placeholders_recursive(filled, answers)
        
        return filled
    
    def _fill_placeholders_recursive(self, obj: Any, answers: Dict[str, Any]):
        """Recursively fill placeholders in any object"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str):
                    obj[key] = self._safe_render_placeholder(value, answers)
                else:
                    self._fill_placeholders_recursive(value, answers)
        elif isinstance(obj, list):
            for item in obj:
                self._fill_placeholders_recursive(item, answers)
    
    def _resolve_triggers(self, filled: Dict[str, Any], ctx: Dict[str, Any]):
        """Resolve triggers with catalog lookup and connection resolution"""
        catalog = ctx.get("catalog", {})
        connections = ctx.get("connections", {})
        user = ctx.get("user", {})
        
        for trigger in filled.get("triggers", []):
            try:
                # Lookup trigger in catalog
                tcat = self._lookup_trigger(catalog, trigger)
                if not tcat:
                    self.report.add_error(
                        "UNKNOWN_TRIGGER",
                        f"triggers.{trigger.get('local_id')}",
                        f"Unknown trigger: {trigger.get('toolkit_slug')}/{trigger.get('trigger_id', trigger.get('slug'))}"
                    )
                    continue
                
                # Enforce supported delivery
                if not self._enforce_supported_delivery(tcat, trigger.get("delivery")):
                    continue
                
                # Resolve connection
                connection_id = self._resolve_connection(connections, tcat, trigger.get("connection_hint"))
                if not connection_id:
                    self.report.add_error(
                        "MISSING_CONNECTION",
                        f"triggers.{trigger.get('local_id')}",
                        f"No connection found for provider {tcat.get('provider')}"
                    )
                    continue
                
                # Set executable trigger data
                trigger["exec"] = {
                    "provider": tcat.get("provider"),
                    "trigger_slug": tcat.get("slug"),
                    "configuration": self._normalize_params(tcat.get("params", {}), trigger.get("configuration", {})),
                    "connection_id": connection_id
                }
                
                # Generate trigger instance ID
                if user.get("id") and filled.get("workflow_id") and filled.get("version"):
                    trigger["trigger_instance_id"] = self._hash_trigger_instance(
                        user["id"], 
                        filled["workflow_id"], 
                        filled["version"], 
                        trigger["local_id"]
                    )
                
            except Exception as e:
                self.report.add_error(
                    "TRIGGER_RESOLUTION_ERROR",
                    f"triggers.{trigger.get('local_id')}",
                    f"Failed to resolve trigger: {str(e)}"
                )
    
    def _resolve_actions(self, filled: Dict[str, Any], ctx: Dict[str, Any]):
        """Resolve actions with catalog lookup and connection resolution"""
        catalog = ctx.get("catalog", {})
        connections = ctx.get("connections", {})
        defaults = ctx.get("defaults", {})
        
        for action in filled.get("actions", []):
            try:
                # Lookup action in catalog
                acat = self._lookup_action(catalog, action)
                if not acat:
                    self.report.add_error(
                        "UNKNOWN_ACTION",
                        f"actions.{action.get('local_id')}",
                        f"Unknown action: {action.get('toolkit_slug')}/{action.get('action_id', action.get('slug'))}"
                    )
                    continue
                
                # Resolve connection
                connection_id = self._resolve_connection(connections, acat, action.get("connection_hint"))
                if not connection_id:
                    self.report.add_error(
                        "MISSING_CONNECTION",
                        f"actions.{action.get('local_id')}",
                        f"No connection found for provider {acat.get('provider')}"
                    )
                    continue
                
                # Coerce and fill required inputs
                required = self._coerce_and_fill_params(acat.get("paramSpec", {}), action.get("required_inputs", {}))
                optional = self._normalize_params(acat.get("paramSpec", {}), action.get("optional_inputs", {}))
                
                # Set executable action data
                action["exec"] = {
                    "provider": acat.get("provider"),
                    "action_slug": acat.get("slug"),
                    "connection_id": connection_id,
                    "required_inputs": required,
                    "optional_inputs": optional,
                    "retry": self._choose_retry(action.get("retry"), defaults.get("retry"), acat.get("policy")),
                    "timeout_ms": self._choose_timeout(action.get("timeout_ms"), defaults.get("timeout_ms"), acat.get("policy")),
                    "rate_limit": self._choose_rate_limit(action.get("rate_limit"), defaults.get("rate_limit"), acat.get("policy"))
                }
                
            except Exception as e:
                self.report.add_error(
                    "ACTION_RESOLUTION_ERROR",
                    f"actions.{action.get('local_id')}",
                    f"Failed to resolve action: {str(e)}"
                )
    
    def _lookup_trigger(self, catalog: Dict[str, Any], trigger: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Lookup trigger in catalog"""
        toolkit_slug = trigger.get("toolkit_slug")
        trigger_id = trigger.get("trigger_id") or trigger.get("slug")
        
        # Search through catalog for matching trigger
        for provider in catalog.get("providers", []):
            for toolkit in provider.get("toolkits", []):
                if toolkit.get("slug") == toolkit_slug:
                    for t in toolkit.get("triggers", []):
                        if t.get("slug") == trigger_id:
                            return {**t, "provider": provider.get("slug")}
        
        return None
    
    def _lookup_action(self, catalog: Dict[str, Any], action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Lookup action in catalog"""
        toolkit_slug = action.get("toolkit_slug")
        action_id = action.get("action_id") or action.get("slug")
        
        # Search through catalog for matching action
        for provider in catalog.get("providers", []):
            for toolkit in provider.get("toolkits", []):
                if toolkit.get("slug") == toolkit_slug:
                    for a in toolkit.get("actions", []):
                        if a.get("slug") == action_id:
                            return {**a, "provider": provider.get("slug")}
        
        return None
    
    def _enforce_supported_delivery(self, tcat: Dict[str, Any], delivery: str) -> bool:
        """Enforce supported delivery methods for triggers"""
        if not delivery:
            return True
        
        supported_delivery = tcat.get("supported_delivery", [])
        if delivery not in supported_delivery:
            self.report.add_error(
                "UNSUPPORTED_DELIVERY",
                "",
                f"Delivery method '{delivery}' not supported by trigger {tcat.get('slug')}",
                f"Supported methods: {', '.join(supported_delivery)}"
            )
            return False
        
        return True
    
    def _resolve_connection(self, connections: Dict[str, Any], catalog_item: Dict[str, Any], hint: Optional[str]) -> Optional[str]:
        """Resolve connection ID for a provider"""
        provider = catalog_item.get("provider")
        
        # If hint provided, try to use it
        if hint and hint in connections:
            connection = connections[hint]
            if connection.get("provider") == provider:
                return hint
        
        # Otherwise, find first connection for this provider
        for conn_id, connection in connections.items():
            if connection.get("provider") == provider:
                return conn_id
        
        return None
    
    def _normalize_params(self, param_spec: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize parameters according to catalog specification"""
        normalized = {}
        
        for param_name, param_value in params.items():
            if param_name in param_spec:
                spec = param_spec[param_name]
                normalized[param_name] = self._coerce_param_value(param_value, spec)
            else:
                # Keep unknown params as-is
                normalized[param_name] = param_value
        
        return normalized
    
    def _coerce_and_fill_params(self, param_spec: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce and fill required parameters"""
        filled = {}
        
        for param_name, spec in param_spec.items():
            if spec.get("required", False):
                if param_name in params:
                    filled[param_name] = self._coerce_param_value(params[param_name], spec)
                else:
                    # Use default if available
                    if "default" in spec:
                        filled[param_name] = spec["default"]
                    else:
                        self.report.add_error(
                            "MISSING_REQUIRED_PARAM",
                            f"params.{param_name}",
                            f"Required parameter '{param_name}' is missing"
                        )
        
        return filled
    
    def _coerce_param_value(self, value: Any, spec: Dict[str, Any]) -> Any:
        """Coerce parameter value according to specification"""
        param_type = spec.get("type", "string")
        
        try:
            if param_type == "number":
                return float(value)
            elif param_type == "integer":
                return int(value)
            elif param_type == "boolean":
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes", "on")
                return bool(value)
            elif param_type == "array" and isinstance(value, str):
                # Handle comma-separated strings as arrays
                return [item.strip() for item in value.split(",")]
            else:
                return value
        except (ValueError, TypeError):
            self.report.add_warning(
                "PARAM_COERCION_FAILED",
                "",
                f"Failed to coerce parameter value '{value}' to type '{param_type}'"
            )
            return value
    
    def _choose_retry(self, action_retry: Optional[Dict], default_retry: Optional[Dict], policy: Optional[Dict]) -> Dict[str, Any]:
        """Choose retry policy for an action"""
        if action_retry:
            return action_retry
        
        if default_retry:
            return default_retry
        
        # Default retry policy
        return {
            "max_attempts": 3,
            "backoff_multiplier": 2.0,
            "initial_delay_ms": 1000
        }
    
    def _choose_timeout(self, action_timeout: Optional[int], default_timeout: Optional[int], policy: Optional[Dict]) -> int:
        """Choose timeout for an action"""
        if action_timeout:
            return action_timeout
        
        if default_timeout:
            return default_timeout
        
        # Default timeout
        return 30000  # 30 seconds
    
    def _choose_rate_limit(self, action_rate_limit: Optional[Dict], default_rate_limit: Optional[Dict], policy: Optional[Dict]) -> Optional[Dict[str, Any]]:
        """Choose rate limit for an action"""
        if action_rate_limit:
            return action_rate_limit
        
        if default_rate_limit:
            return default_rate_limit
        
        # Default rate limit
        return {
            "requests_per_minute": 60
        }
    
    def _inject_default_policies(self, filled: Dict[str, Any], defaults: Dict[str, Any]):
        """Inject default policies into the workflow"""
        if "policies" not in filled:
            filled["policies"] = {}
        
        policies = filled["policies"]
        
        # Set default policies if not specified
        if "retry" not in policies and "retry" in defaults:
            policies["retry"] = defaults["retry"]
        
        if "timeout_ms" not in policies and "timeout_ms" in defaults:
            policies["timeout_ms"] = defaults["timeout_ms"]
        
        if "rate_limit" not in policies and "rate_limit" in defaults:
            policies["rate_limit"] = defaults["rate_limit"]
    
    def _reject_plaintext_secrets(self, filled: Dict[str, Any], connections: Dict[str, Any]):
        """Reject any plaintext secrets and replace with references"""
        # This is a placeholder for secret validation logic
        # In a real implementation, you'd scan for common secret patterns
        # and replace them with connection references
        
        # For now, just add a warning if we find suspicious patterns
        suspicious_patterns = ["password", "secret", "key", "token", "api_key"]
        
        def scan_for_secrets(obj: Any, path: str = ""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(key, str) and any(pattern in key.lower() for pattern in suspicious_patterns):
                        if isinstance(value, str) and len(value) > 10:
                            self.report.add_warning(
                                "POTENTIAL_SECRET",
                                current_path,
                                "Potential secret found - consider using connection references"
                            )
                    scan_for_secrets(value, current_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    scan_for_secrets(item, f"{path}[{i}]")
        
        scan_for_secrets(filled)
    
    def _attempt_repair(self, filled: Dict[str, Any], ctx: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Attempt to repair common issues"""
        repairs = []
        patched = copy.deepcopy(filled)
        
        # Add any auto-repair logic here
        # For now, just return the original with empty repairs
        
        return patched, repairs
    
    def _validate_executable(self, executable_doc: Dict[str, Any]) -> bool:
        """Validate the final executable document"""
        # Check that all triggers and actions have exec blocks
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
