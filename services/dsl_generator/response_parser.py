"""
Response Parser for DSL Generator

Handles parsing and validation of Claude responses, extracting
missing fields, and calculating confidence scores.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from .models import GenerationResponse, MissingField, GenerationContext

logger = logging.getLogger(__name__)


class ResponseParser:
    """
    Parses and validates Claude responses for workflow generation.
    
    Responsibilities:
    - Parsing Claude API responses
    - Validating DSL structure
    - Extracting missing fields
    - Calculating confidence scores
    - Extracting suggested apps
    """
    
    def __init__(self):
        """Initialize the response parser"""
        pass
    
    async def parse_response(
        self, 
        claude_response: str, 
        context: GenerationContext
    ) -> GenerationResponse:
        """Parse and validate the Claude response"""
        logger.info(f"[LINE 35] parse_response called with response length: {len(claude_response)}")
        logger.info(f"[LINE 36] Context type: {type(context)}")
        logger.info(f"[LINE 37] Context request: {getattr(context, 'request', 'N/A')}")
        
        try:
            logger.info(f"[LINE 39] Parsing Claude response (length: {len(claude_response)} chars)")
            logger.debug(f"[LINE 40] Raw response: {claude_response[:500]}...")
            
            # Extract JSON from response (remove any markdown formatting)
            logger.info(f"[LINE 43] Extracting JSON from response...")
            json_start = claude_response.find('{')
            json_end = claude_response.rfind('}') + 1
            logger.info(f"[LINE 44] JSON boundaries: start={json_start}, end={json_end}")
            
            if json_start == -1 or json_end == 0:
                logger.error(f"[LINE 46] No valid JSON found in Claude response")
                logger.debug(f"[LINE 47] Response content: {claude_response}")
                raise ValueError("No valid JSON found in Claude response")
            
            json_str = claude_response[json_start:json_end]
            logger.info(f"[LINE 50] Extracted JSON string (length: {len(json_str)} chars)")
            logger.debug(f"[LINE 51] Extracted JSON string: {json_str[:500]}...")
            
            try:
                logger.info(f"[LINE 53] Parsing JSON string...")
                dsl_template = json.loads(json_str)
                logger.info(f"[LINE 54] JSON parsing successful")
            except json.JSONDecodeError as e:
                logger.error(f"[LINE 56] JSON parsing failed: {e}")
                logger.debug(f"[LINE 57] JSON string: {json_str}")
                raise ValueError(f"Invalid JSON in Claude response: {e}")
            
            logger.info(f"[LINE 60] Successfully parsed JSON with keys: {list(dsl_template.keys())}")
            logger.info(f"[LINE 61] DSL template type: {type(dsl_template)}")
            logger.debug(f"[LINE 62] DSL template content: {json.dumps(dsl_template, indent=2)[:1000]}...")
            
            # Attempt to fix common structural issues
            logger.info(f"[LINE 65] Attempting to fix common structural issues...")
            dsl_template = self._attempt_structure_fix(dsl_template)
            logger.info(f"[LINE 66] Applied structure fixes if needed")
            logger.info(f"[LINE 67] DSL template after fixes: {list(dsl_template.keys())}")
            
            # Validate basic structure
            logger.info(f"[LINE 69] Validating DSL structure...")
            if not self._validate_dsl_structure(dsl_template):
                logger.error(f"[LINE 70] Generated DSL does not match expected structure")
                logger.error(f"[LINE 71] DSL template keys: {list(dsl_template.keys())}")
                logger.debug(f"[LINE 72] DSL template: {json.dumps(dsl_template, indent=2)}")
                raise ValueError("Generated DSL does not match expected structure")
            
            logger.info(f"[LINE 75] DSL structure validation passed")
            
            # Extract missing fields
            logger.info(f"[LINE 77] Extracting missing fields...")
            missing_fields = self._extract_missing_fields(dsl_template, context)
            logger.info(f"[LINE 78] Extracted {len(missing_fields)} missing fields: {missing_fields}")
            
            # Calculate confidence based on completeness
            logger.info(f"[LINE 81] Calculating confidence...")
            confidence = self._calculate_confidence(dsl_template, missing_fields)
            logger.info(f"[LINE 82] Calculated confidence: {confidence}")
            
            logger.info(f"[LINE 84] Successfully parsed response with {len(missing_fields)} missing fields, confidence: {confidence}")
            
            # Extract suggested apps
            logger.info(f"[LINE 86] Extracting suggested apps...")
            suggested_apps = self._extract_suggested_apps(dsl_template)
            logger.info(f"[LINE 87] Extracted suggested apps: {suggested_apps}")
            
            # Create generation metadata
            generation_metadata = {
                "model": "claude-3-5-sonnet-20241022",
                "timestamp": datetime.utcnow().isoformat(),
                "workflow_type": context.request.workflow_type,
                "complexity": context.request.complexity
            }
            logger.info(f"[LINE 95] Created generation metadata: {generation_metadata}")
            
            response = GenerationResponse(
                success=True,
                dsl_template=dsl_template,
                missing_fields=missing_fields,
                confidence=confidence,
                reasoning="Workflow generated successfully based on user request and available catalog data",
                suggested_apps=suggested_apps,
                generation_metadata=generation_metadata,
                raw_response=claude_response
            )
            logger.info(f"[LINE 105] Created GenerationResponse: success={response.success}, confidence={response.confidence}")
            
            return response
            
        except Exception as e:
            logger.error(f"[LINE 108] Failed to parse Claude response: {e}")
            logger.error(f"[LINE 109] Exception type: {type(e).__name__}")
            logger.error(f"[LINE 110] Exception details: {str(e)}")
            logger.debug(f"[LINE 111] Full response content: {claude_response}")
            
            return GenerationResponse(
                success=False,
                error_message=f"Failed to parse Claude response: {e}",
                missing_fields=[],
                confidence=0.0
            )
    
    def _validate_dsl_structure(self, dsl_template: Dict[str, Any]) -> bool:
        """Validate that the DSL template has the basic required structure"""
        logger.info(f"[LINE 108] _validate_dsl_structure called with template keys: {list(dsl_template.keys())}")
        
        # Get the schema type
        schema_type = dsl_template.get("schema_type")
        logger.info(f"[LINE 111] Extracted schema_type: {schema_type}")
        
        if not schema_type:
            logger.warning(f"[LINE 113] No schema_type found in DSL template")
            logger.warning(f"[LINE 114] Available keys: {list(dsl_template.keys())}")
            return False
        
        # Define required fields based on actual schema
        required_fields = {
            "template": ["schema_type", "workflow"],
            "executable": ["schema_type", "workflow", "connections"],
            "dag": ["schema_type", "nodes", "edges"]
        }
        logger.info(f"[LINE 121] Required fields for {schema_type}: {required_fields.get(schema_type, [])}")
        
        if schema_type not in required_fields:
            logger.warning(f"[LINE 124] Unknown schema_type: {schema_type}")
            logger.warning(f"[LINE 125] Valid schema types: {list(required_fields.keys())}")
            return False
        
        required = required_fields[schema_type]
        logger.info(f"[LINE 128] Using required fields: {required}")
        
        # Check if all required fields are present
        missing_fields = [field for field in required if field not in dsl_template]
        logger.info(f"[LINE 131] Checking for missing fields: {missing_fields}")
        
        if missing_fields:
            logger.warning(f"[LINE 133] Missing required fields for {schema_type}: {missing_fields}")
            logger.warning(f"[LINE 134] Available fields: {list(dsl_template.keys())}")
            return False
        
        logger.info(f"[LINE 137] All required fields present for {schema_type}")
        
        # Additional validation for specific schema types
        if schema_type == "template":
            logger.info(f"[LINE 140] Validating template schema...")
            # For templates, ensure workflow has basic structure
            workflow = dsl_template.get("workflow", {})
            logger.info(f"[LINE 143] Workflow object: {workflow}")
            logger.info(f"[LINE 144] Workflow type: {type(workflow)}")
            
            if not isinstance(workflow, dict):
                logger.warning(f"[LINE 146] Template workflow must be an object, got: {type(workflow)}")
                return False
            
            # Check for basic workflow fields (but don't require all)
            workflow_name = workflow.get("name")
            workflow_description = workflow.get("description")
            logger.info(f"[LINE 151] Workflow name: {workflow_name}")
            logger.info(f"[LINE 152] Workflow description: {workflow_description}")
            
            if not workflow_name and not workflow_description:
                logger.warning(f"[LINE 154] Template workflow should have name or description")
                logger.warning(f"[LINE 155] Workflow keys: {list(workflow.keys())}")
                # Don't fail validation for this, just warn
        
        elif schema_type == "executable":
            logger.info(f"[LINE 158] Validating executable schema...")
            # For executables, ensure connections is an array
            connections = dsl_template.get("connections", [])
            logger.info(f"[LINE 161] Connections: {connections}")
            logger.info(f"[LINE 162] Connections type: {type(connections)}")
            
            if not isinstance(connections, list):
                logger.warning(f"[LINE 164] Executable connections must be an array, got: {type(connections)}")
                return False
        
        elif schema_type == "dag":
            logger.info(f"[LINE 167] Validating DAG schema...")
            # For DAGs, ensure nodes and edges are arrays
            nodes = dsl_template.get("nodes", [])
            edges = dsl_template.get("edges", [])
            logger.info(f"[LINE 170] Nodes: {nodes}")
            logger.info(f"[LINE 171] Edges: {edges}")
            logger.info(f"[LINE 172] Nodes type: {type(nodes)}")
            logger.info(f"[LINE 173] Edges type: {type(edges)}")
            
            if not isinstance(nodes, list) or not isinstance(edges, list):
                logger.warning(f"[LINE 175] DAG nodes and edges must be arrays")
                logger.warning(f"[LINE 176] Nodes type: {type(nodes)}, Edges type: {type(edges)}")
                return False
        
        logger.info(f"[LINE 179] DSL structure validation passed for {schema_type}")
        return True
    
    def _attempt_structure_fix(self, dsl_template: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to fix common structural issues in the generated DSL"""
        schema_type = dsl_template.get("schema_type")
        if not schema_type:
            return dsl_template
        
        fixed_template = dsl_template.copy()
        
        # Fix common issues
        if schema_type == "template":
            # Ensure workflow exists
            if "workflow" not in fixed_template:
                fixed_template["workflow"] = {
                    "name": "Generated Workflow",
                    "description": "Workflow generated from user request",
                    "triggers": [],
                    "actions": []
                }
            
            # Ensure missing_information exists
            if "missing_information" not in fixed_template:
                fixed_template["missing_information"] = []
            
            # Ensure confidence exists
            if "confidence" not in fixed_template:
                fixed_template["confidence"] = 80
        
        elif schema_type == "executable":
            # Ensure connections exists
            if "connections" not in fixed_template:
                fixed_template["connections"] = []
        
        elif schema_type == "dag":
            # Ensure nodes and edges exist
            if "nodes" not in fixed_template:
                fixed_template["nodes"] = []
            if "edges" not in fixed_template:
                fixed_template["edges"] = []
        
        return fixed_template
    
    def _extract_missing_fields(
        self, 
        dsl_template: Dict[str, Any], 
        context: GenerationContext
    ) -> List[MissingField]:
        """Extract fields that need user input"""
        missing_fields = []
        
        # Extract from missing_information if present (template schema)
        if "missing_information" in dsl_template:
            for info in dsl_template["missing_information"]:
                missing_fields.append(MissingField(
                    field=info.get("field", ""),
                    prompt=info.get("prompt", ""),
                    type=info.get("type", "string"),
                    required=info.get("required", True)
                ))
        
        # Extract from connections if present (executable schema)
        if "connections" in dsl_template:
            for connection in dsl_template["connections"]:
                if not connection.get("connection_id"):
                    missing_fields.append(MissingField(
                        field=f"connections.{connection.get('toolkit_slug', 'unknown')}.connection_id",
                        prompt=f"Please provide connection ID for {connection.get('toolkit_slug', 'unknown')}",
                        type="string",
                        required=True
                    ))
        
        return missing_fields
    
    def _calculate_confidence(self, dsl_template: Dict[str, Any], missing_fields: List[MissingField]) -> float:
        """Calculate confidence score based on completeness and structure"""
        base_confidence = 0.5
        
        # Bonus for having required fields
        if dsl_template.get("schema_type"):
            base_confidence += 0.2
        
        if dsl_template.get("workflow"):
            base_confidence += 0.1
        
        # Bonus for having triggers and actions
        workflow = dsl_template.get("workflow", {})
        if workflow.get("triggers"):
            base_confidence += 0.1
        
        if workflow.get("actions"):
            base_confidence += 0.1
        
        # Penalty for missing fields
        missing_penalty = min(0.3, len(missing_fields) * 0.1)
        base_confidence -= missing_penalty
        
        # Structure bonus (we already validated this, so just check if it has the right keys)
        if dsl_template.get("schema_type") and dsl_template.get("workflow"):
            structure_bonus = 0.1
        else:
            structure_bonus = 0.0
        
        final_confidence = min(1.0, max(0.0, base_confidence + structure_bonus))
        return round(final_confidence, 2)
    
    def _extract_suggested_apps(self, dsl_template: Dict[str, Any]) -> List[str]:
        """Extract suggested apps from the generated template"""
        suggested_apps = []
        
        # Extract from toolkit metadata
        if "toolkit" in dsl_template:
            toolkit = dsl_template["toolkit"]
            if "slug" in toolkit:
                suggested_apps.append(toolkit["slug"])
        
        # Extract from workflow actions and triggers
        if "workflow" in dsl_template:
            workflow = dsl_template["workflow"]
            
            # Extract from triggers
            if "triggers" in workflow:
                for trigger in workflow["triggers"]:
                    if "toolkit_slug" in trigger:
                        suggested_apps.append(trigger["toolkit_slug"])
            
            # Extract from actions
            if "actions" in workflow:
                for action in workflow["actions"]:
                    if "toolkit_slug" in action:
                        suggested_apps.append(action["toolkit_slug"])
        
        # Remove duplicates and return
        return list(set(suggested_apps))
    
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
