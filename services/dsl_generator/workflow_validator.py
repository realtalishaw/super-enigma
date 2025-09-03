"""
Workflow Validator for DSL Generator

Handles validation of generated workflows against schemas,
catalog data, and business rules.
"""

import logging
from typing import Dict, Any, List
from core.validator import validate, lint, Stage, LintContext
from .models import GenerationContext

logger = logging.getLogger(__name__)


class WorkflowValidator:
    """
    Validates generated workflows against schemas and catalog data.
    
    Responsibilities:
    - Schema validation using core validator
    - Linting with business rules
    - Catalog compliance verification
    - Validation result formatting
    """
    
    def __init__(self):
        """Initialize the workflow validator"""
        pass
    
    async def validate_generated_workflow(
        self,
        dsl_template: Dict[str, Any],
        context: GenerationContext,
        workflow_type: str
    ) -> Dict[str, Any]:
        """
        Validate the generated workflow against schema and catalog.
        
        Args:
            dsl_template: The generated DSL template
            context: Generation context with catalog data
            workflow_type: Type of workflow being validated
            
        Returns:
            Validation result with is_valid flag and any errors
        """
        logger.info(f"[LINE 35] validate_generated_workflow called")
        logger.info(f"[LINE 36] DSL template keys: {list(dsl_template.keys())}")
        logger.info(f"[LINE 37] Workflow type: {workflow_type}")
        logger.info(f"[LINE 38] Context type: {type(context)}")
        
        try:
            # Determine the stage for validation
            stage_map = {
                "template": Stage.TEMPLATE,
                "executable": Stage.EXECUTABLE,
                "dag": Stage.DAG
            }
            stage = stage_map.get(workflow_type, Stage.TEMPLATE)
            logger.info(f"[LINE 46] Mapped workflow_type '{workflow_type}' to stage: {stage}")
            
            # Create linting context using the actual catalog manager cache, not mock data
            # Pass through the raw providers dict if available to maximize validator fidelity
            providers = getattr(context.catalog, 'available_providers', None)
            logger.info(f"[LINE 49] Context catalog available_providers type: {type(providers)}")
            logger.info(f"[LINE 50] Context catalog available_providers count: {len(providers) if isinstance(providers, (list, dict)) else 'N/A'}")
            
            if isinstance(providers, list):
                logger.info(f"[LINE 52] Providers is a list, converting to catalog object...")
                # Convert list of providers to a simple catalog object with lookup helpers
                provider_index = {p.get('slug'): p for p in providers if p and p.get('slug')}
                logger.info(f"[LINE 54] Created provider index with {len(provider_index)} providers")
                logger.info(f"[LINE 55] Provider index keys: {list(provider_index.keys())}")
                
                class SimpleCatalog:
                    async def get_provider_by_slug(self_inner, slug):
                        logger.debug(f"[LINE 57] SimpleCatalog.get_provider_by_slug called with slug: '{slug}'")
                        result = provider_index.get(slug)
                        logger.debug(f"[LINE 58] SimpleCatalog.get_provider_by_slug result: {result is not None}")
                        return result
                    async def get_tool_by_slug(self_inner, action_name, toolkit_slug):
                        logger.debug(f"[LINE 60] SimpleCatalog.get_tool_by_slug called with action_name: '{action_name}', toolkit_slug: '{toolkit_slug}'")
                        prov = provider_index.get(toolkit_slug)
                        if not prov:
                            logger.debug(f"[LINE 62] No provider found for toolkit_slug: '{toolkit_slug}'")
                            return None
                        for a in prov.get('actions', []) or []:
                            if a.get('action_name') == action_name or a.get('name') == action_name:
                                logger.debug(f"[LINE 65] Found action '{action_name}' in provider '{toolkit_slug}'")
                                return a
                        logger.debug(f"[LINE 67] Action '{action_name}' not found in provider '{toolkit_slug}'")
                        return None
                    async def get_catalog(self_inner):
                        logger.debug(f"[LINE 69] SimpleCatalog.get_catalog called")
                        return {"providers": list(provider_index.values())}
                catalog_for_lint = SimpleCatalog()
                logger.info(f"[LINE 71] Created SimpleCatalog for linting")
                
            elif isinstance(providers, dict):
                logger.info(f"[LINE 73] Providers is a dict, creating DictCatalog...")
                # If a dict, expose a minimal interface
                class DictCatalog:
                    async def get_provider_by_slug(self_inner, slug):
                        logger.debug(f"[LINE 76] DictCatalog.get_provider_by_slug called with slug: '{slug}'")
                        result = providers.get(slug)
                        logger.debug(f"[LINE 77] DictCatalog.get_provider_by_slug result: {result is not None}")
                        return result
                    async def get_tool_by_slug(self_inner, action_name, toolkit_slug):
                        logger.debug(f"[LINE 79] DictCatalog.get_tool_by_slug called with action_name: '{action_name}', toolkit_slug: '{toolkit_slug}'")
                        prov = providers.get(toolkit_slug)
                        if not prov:
                            logger.debug(f"[LINE 81] No provider found for toolkit_slug: '{toolkit_slug}'")
                            return None
                        for a in prov.get('actions', []) or []:
                            if a.get('action_name') == action_name or a.get('name') == action_name:
                                logger.debug(f"[LINE 84] Found action '{action_name}' in provider '{toolkit_slug}'")
                                return a
                        logger.debug(f"[LINE 86] Action '{action_name}' not found in provider '{toolkit_slug}'")
                        return None
                    async def get_catalog(self_inner):
                        logger.debug(f"[LINE 88] DictCatalog.get_catalog called")
                        return {"providers": list(providers.values())}
                catalog_for_lint = DictCatalog()
                logger.info(f"[LINE 90] Created DictCatalog for linting")
                
            else:
                logger.warning(f"[LINE 92] Providers is neither list nor dict, using EmptyCatalog...")
                # Fallback to empty but present catalog
                class EmptyCatalog:
                    async def get_provider_by_slug(self_inner, slug):
                        logger.debug(f"[LINE 95] EmptyCatalog.get_provider_by_slug called with slug: '{slug}'")
                        return None
                    async def get_tool_by_slug(self_inner, action_name, toolkit_slug):
                        logger.debug(f"[LINE 97] EmptyCatalog.get_tool_by_slug called with action_name: '{action_name}', toolkit_slug: '{toolkit_slug}'")
                        return None
                    async def get_catalog(self_inner):
                        logger.debug(f"[LINE 99] EmptyCatalog.get_catalog called")
                        return {"providers": []}
                catalog_for_lint = EmptyCatalog()
                logger.info(f"[LINE 101] Created EmptyCatalog for linting")
            
            logger.info(f"[LINE 103] Created catalog_for_lint: {type(catalog_for_lint)}")
            
            # Create linting context with correct parameters
            lint_context = LintContext(
                catalog=catalog_for_lint,
                connections={}  # Empty connections for now
            )
            logger.info(f"[LINE 108] Created LintContext with catalog: {type(catalog_for_lint)}")
            
            # Perform validation
            logger.info(f"[LINE 110] Starting schema validation...")
            validation_response = await validate(stage, dsl_template)
            logger.info(f"[LINE 111] Schema validation result: {validation_response}")
            
            # Perform linting
            logger.info(f"[LINE 113] Starting linting...")
            lint_report = await lint(stage, dsl_template, lint_context)
            logger.info(f"[LINE 114] Lint result: {lint_report}")
            
            # Combine results
            is_valid = validation_response.ok
            validation_errors = validation_response.errors
            lint_errors = lint_report.errors
            lint_warnings = lint_report.warnings
            lint_hints = lint_report.hints
            
            logger.info(f"[LINE 120] Combined validation results:")
            logger.info(f"[LINE 121] - is_valid: {is_valid}")
            logger.info(f"[LINE 122] - validation_errors count: {len(validation_errors)}")
            logger.info(f"[LINE 123] - lint_errors count: {len(lint_errors)}")
            logger.info(f"[LINE 124] - lint_warnings count: {len(lint_warnings)}")
            logger.info(f"[LINE 125] - lint_hints count: {len(lint_hints)}")
            
            if validation_errors:
                logger.warning(f"[LINE 127] Validation errors: {validation_errors}")
            if lint_errors:
                logger.warning(f"[LINE 129] Lint errors: {lint_errors}")
            if lint_warnings:
                logger.warning(f"[LINE 131] Lint warnings: {lint_warnings}")
            if lint_hints:
                logger.info(f"[LINE 133] Lint hints: {lint_hints}")
            
            return {
                'is_valid': is_valid,
                'validation_errors': validation_errors,
                'lint_errors': lint_errors,
                'lint_warnings': lint_warnings,
                'lint_hints': lint_hints,
                'stage': stage.value if hasattr(stage, 'value') else str(stage)
            }
            
        except Exception as e:
            logger.error(f"[LINE 140] Error in validate_generated_workflow: {e}")
            logger.error(f"[LINE 141] Exception type: {type(e).__name__}")
            logger.error(f"[LINE 142] Exception details: {str(e)}")
            return {
                'is_valid': False,
                'validation_errors': [f"Validation exception: {e}"],
                'lint_errors': [],
                'lint_warnings': [],
                'lint_hints': [],
                'stage': 'unknown'
            }
    
    def validate_workflow_components(self, workflow_data: Dict[str, Any], catalog_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate specific workflow components against the catalog"""
        if not catalog_data:
            return {"valid": False, "error": "No catalog data available"}
        
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "validated_components": {}
        }
        
        # Validate triggers
        if 'triggers' in workflow_data:
            for trigger in workflow_data['triggers']:
                provider = trigger.get('provider')
                trigger_name = trigger.get('name')
                if provider and trigger_name:
                    if provider not in catalog_data:
                        validation_results["errors"].append(f"Unknown provider: {provider}")
                        validation_results["valid"] = False
                    else:
                        available_triggers = self._get_provider_triggers(catalog_data, provider)
                        if trigger_name not in available_triggers:
                            validation_results["errors"].append(f"Unknown trigger '{trigger_name}' for provider '{provider}'")
                            validation_results["valid"] = False
                        else:
                            validation_results["validated_components"][f"trigger_{provider}"] = "valid"
        
        # Validate actions
        if 'actions' in workflow_data:
            for action in workflow_data['actions']:
                provider = action.get('provider')
                action_name = action.get('name')
                if provider and action_name:
                    if provider not in catalog_data:
                        validation_results["errors"].append(f"Unknown provider: {provider}")
                        validation_results["valid"] = False
                    else:
                        available_actions = self._get_provider_actions(catalog_data, provider)
                        if action_name not in available_actions:
                            validation_results["errors"].append(f"Unknown action '{action_name}' for provider '{provider}'")
                            validation_results["valid"] = False
                        else:
                            validation_results["validated_components"][f"action_{provider}"] = "valid"
        
        return validation_results
    
    def _get_provider_actions(self, catalog_data: Dict[str, Any], provider_slug: str) -> List[str]:
        """Get list of available actions for a specific provider"""
        if provider_slug not in catalog_data:
            return []
        
        provider = catalog_data[provider_slug]
        return [action.get('name', 'Unknown') for action in provider.get('actions', [])]
    
    def _get_provider_triggers(self, catalog_data: Dict[str, Any], provider_slug: str) -> List[str]:
        """Get list of available triggers for a specific provider"""
        if provider_slug not in catalog_data:
            return []
        
        provider = catalog_data[provider_slug]
        return [trigger.get('name', 'Unknown') for trigger in provider.get('triggers', [])]
    
    def verify_catalog_compliance(
        self,
        dsl_template: Dict[str, Any],
        catalog_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verify that the generated workflow only uses tools available in the catalog.
        
        Args:
            dsl_template: The generated DSL template
            catalog_data: Available catalog data
            
        Returns:
            Compliance result with is_compliant flag and any errors
        """
        errors = []
        
        try:
            # Extract available toolkits, triggers, and actions
            available_toolkits = set(catalog_data.keys())
            available_triggers = set()
            available_actions = set()
            
            # Collect all available actions and triggers from all providers
            for provider in catalog_data.values():
                for action in provider.get('actions', []):
                    available_actions.add(action.get('action_name', ''))
                for trigger in provider.get('triggers', []):
                    available_triggers.add(trigger.get('id', ''))
            
            # Check toolkit references
            if 'toolkit' in dsl_template and 'slug' in dsl_template['toolkit']:
                toolkit_slug = dsl_template['toolkit']['slug']
                if toolkit_slug not in available_toolkits:
                    errors.append(f"Unknown toolkit: {toolkit_slug}")
            
            # Check workflow triggers and actions
            if 'workflow' in dsl_template:
                workflow = dsl_template['workflow']
                
                # Check triggers
                if 'triggers' in workflow:
                    for trigger in workflow['triggers']:
                        if 'toolkit_slug' in trigger:
                            toolkit_slug = trigger['toolkit_slug']
                            if toolkit_slug not in available_toolkits:
                                errors.append(f"Unknown toolkit in trigger: {toolkit_slug}")
                        
                        if 'trigger_id' in trigger:
                            trigger_id = trigger['trigger_id']
                            if trigger_id not in available_triggers:
                                errors.append(f"Unknown trigger: {trigger_id}")
                
                # Check actions
                if 'actions' in workflow:
                    for action in workflow['actions']:
                        if 'toolkit_slug' in action:
                            toolkit_slug = action['toolkit_slug']
                            if toolkit_slug not in available_toolkits:
                                errors.append(f"Unknown toolkit in action: {toolkit_slug}")
                        
                        if 'action_name' in action:
                            action_name = action['action_name']
                            if action_name not in available_actions:
                                errors.append(f"Unknown action: {action_name}")
            
            # Check connections (for executable workflows)
            if 'connections' in dsl_template:
                for connection in dsl_template['connections']:
                    if 'toolkit_slug' in connection:
                        toolkit_slug = connection['toolkit_slug']
                        if toolkit_slug not in available_toolkits:
                            errors.append(f"Unknown toolkit in connection: {toolkit_slug}")
            
            # Check nodes (for DAG workflows)
            if 'nodes' in dsl_template:
                for node in dsl_template['nodes']:
                    if 'data' in node and 'toolkit_slug' in node['data']:
                        toolkit_slug = node['data']['toolkit_slug']
                        if toolkit_slug not in available_toolkits:
                            errors.append(f"Unknown toolkit in node: {toolkit_slug}")
                    
                    if 'data' in node and 'action_name' in node['data']:
                        action_name = node['data']['action_name']
                        if action_name not in available_actions:
                            errors.append(f"Unknown action in node: {action_name}")
            
            return {
                'is_compliant': len(errors) == 0,
                'errors': errors,
                'available_toolkits_count': len(available_toolkits),
                'available_triggers_count': len(available_triggers),
                'available_actions_count': len(available_actions)
            }
            
        except Exception as e:
            logger.error(f"Catalog compliance check failed: {e}")
            return {
                'is_compliant': False,
                'errors': [f"Compliance check exception: {e}"],
                'available_toolkits_count': 0,
                'available_triggers_count': 0,
                'available_actions_count': 0
            }
    
    def check_catalog_sufficiency(self, context: Any) -> Dict[str, Any]:
        """Check if the catalog has sufficient data to generate meaningful workflows"""
        logger.info(f"[LINE 340] check_catalog_sufficiency called")
        logger.info(f"[LINE 341] Context type: {type(context)}")
        
        # Handle both GenerationContext objects and dict objects (pruned catalog context)
        if hasattr(context, 'catalog'):
            # GenerationContext object
            catalog = context.catalog
            logger.info(f"[LINE 344] Context catalog type: {type(catalog)}")
            
            # Check if available_providers exists
            available_providers = getattr(catalog, 'available_providers', None)
            logger.info(f"[LINE 347] Available providers type: {type(available_providers)}")
            logger.info(f"[LINE 348] Available providers count: {len(available_providers) if isinstance(available_providers, (list, dict)) else 'N/A'}")
            
            if not available_providers:
                logger.warning(f"[LINE 350] No providers available in catalog")
                return {
                    'sufficient': False,
                    'reason': 'No providers available in catalog'
                }
            
            # Check if available_actions exists
            available_actions = getattr(catalog, 'available_actions', None)
            logger.info(f"[LINE 357] Available actions type: {type(available_actions)}")
            logger.info(f"[LINE 358] Available actions count: {len(available_actions) if isinstance(available_actions, (list, dict)) else 'N/A'}")
            
            if not available_actions:
                logger.warning(f"[LINE 360] No actions available in catalog")
                return {
                    'sufficient': False,
                    'reason': 'No actions available in catalog'
                }
            
            # Check minimum requirements
            min_providers = 1
            min_actions = 1
            logger.info(f"[LINE 367] Minimum requirements: providers={min_providers}, actions={min_actions}")
            
            provider_count = len(available_providers) if isinstance(available_providers, (list, dict)) else 0
            action_count = len(available_actions) if isinstance(available_actions, (list, dict)) else 0
            
            logger.info(f"[LINE 370] Current counts: providers={provider_count}, actions={action_count}")
            
            if provider_count < min_providers:
                logger.warning(f"[LINE 372] Insufficient providers: {provider_count} < {min_providers}")
                return {
                    'sufficient': False,
                    'reason': f'Insufficient providers: {provider_count} < {min_providers}'
                }
            
            if action_count < min_actions:
                logger.warning(f"[LINE 377] Insufficient actions: {action_count} < {min_actions}")
                return {
                    'sufficient': False,
                    'reason': f'Insufficient actions: {action_count} < {min_actions}'
                }
        
        elif isinstance(context, dict):
            # Dict object (pruned catalog context from RAG workflow)
            logger.info(f"[LINE 382] Handling dict context (pruned catalog context)")
            
            # Check if providers exist
            providers = context.get('providers', {})
            triggers = context.get('triggers', [])
            actions = context.get('actions', [])
            
            logger.info(f"[LINE 387] Pruned context: providers={len(providers)}, triggers={len(triggers)}, actions={len(actions)}")
            
            if not providers:
                logger.warning(f"[LINE 389] No providers available in pruned context")
                return {
                    'sufficient': False,
                    'reason': 'No providers available in pruned context'
                }
            
            if not actions:
                logger.warning(f"[LINE 394] No actions available in pruned context")
                return {
                    'sufficient': False,
                    'reason': 'No actions available in pruned context'
                }
            
            # Check minimum requirements
            min_providers = 1
            min_actions = 1
            
            if len(providers) < min_providers:
                logger.warning(f"[LINE 401] Insufficient providers: {len(providers)} < {min_providers}")
                return {
                    'sufficient': False,
                    'reason': f'Insufficient providers: {len(providers)} < {min_providers}'
                }
            
            if len(actions) < min_actions:
                logger.warning(f"[LINE 406] Insufficient actions: {len(actions)} < {min_actions}")
                return {
                    'sufficient': False,
                    'reason': f'Insufficient actions: {len(actions)} < {min_actions}'
                }
        else:
            # Unknown context type
            logger.error(f"[LINE 411] Unknown context type: {type(context)}")
            return {
                'sufficient': False,
                'reason': f'Unknown context type: {type(context)}'
            }
        
        # If we get here, the catalog is sufficient
        logger.info(f"[LINE 416] Catalog sufficiency check passed")
        return {
            'sufficient': True,
            'reason': 'Catalog has sufficient data for workflow generation'
        }
