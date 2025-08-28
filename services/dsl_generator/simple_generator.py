"""
Simple Workflow Generator - Does one thing well: generates valid workflows
"""

import json
import logging
from typing import Dict, Any, List, Optional
from .ai_client import AIClient
from .models import GenerationRequest, GenerationResponse

logger = logging.getLogger(__name__)


class SimpleWorkflowGenerator:
    """
    Generates workflows using AI with real catalog data.
    No abstractions, no complexity - just works.
    """
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.ai_client = AIClient(anthropic_api_key)
        self._catalog_cache = {}
    
    def set_catalog_cache(self, catalog_cache: Dict[str, Any]):
        """Set the catalog data directly"""
        self._catalog_cache = catalog_cache
    
    async def generate_workflow(self, request: GenerationRequest) -> GenerationResponse:
        """Generate a workflow from user request"""
        try:
            # Get available tools
            available_tools = self._get_available_tools(request.selected_apps)
            
            if not available_tools:
                return GenerationResponse(
                    success=False,
                    error_message="No tools available for selected apps"
                )
            
            # Build simple prompt
            prompt = self._build_prompt(request.user_prompt, available_tools)
            
            # Call AI
            response = await self.ai_client.generate_workflow(prompt)
            
            # Debug: log the response
            logger.info(f"AI Response: {response}")
            
            # Parse response
            try:
                # Clean the response - remove any markdown formatting
                cleaned_response = response.strip()
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]
                cleaned_response = cleaned_response.strip()
                
                logger.info(f"Cleaned response: {cleaned_response}")
                
                workflow_json = json.loads(cleaned_response)
                return GenerationResponse(
                    success=True,
                    dsl_template=workflow_json,
                    confidence=0.8
                )
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Raw response was: {repr(response)}")
                return GenerationResponse(
                    success=False,
                    error_message=f"Invalid JSON response: {str(e)}"
                )
                
        except Exception as e:
            logger.error(f"Workflow generation failed: {e}")
            return GenerationResponse(
                success=False,
                error_message=str(e)
            )
    
    def _get_available_tools(self, selected_apps: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get available tools from catalog cache"""
        if not self._catalog_cache:
            return {}
        
        tools = {"triggers": [], "actions": [], "toolkits": []}
        
        # Get toolkits
        toolkits = self._catalog_cache.get("toolkits", {})
        
        # Filter by selected apps if provided
        if selected_apps:
            filtered_toolkits = {k: v for k, v in toolkits.items() if k in selected_apps}
        else:
            filtered_toolkits = toolkits
        
        # Build tools list
        for toolkit_slug, toolkit_data in filtered_toolkits.items():
            tools["toolkits"].append({
                "slug": toolkit_slug,
                "name": toolkit_data.get("name", toolkit_slug)
            })
            
            # Add triggers
            for trigger in toolkit_data.get("triggers", []):
                tools["triggers"].append({
                    "toolkit_slug": toolkit_slug,
                    "trigger_slug": trigger.get("slug"),
                    "name": trigger.get("name")
                })
            
            # Add actions
            for action in toolkit_data.get("actions", []):
                tools["actions"].append({
                    "toolkit_slug": toolkit_slug,
                    "action_name": action.get("slug"),
                    "name": action.get("name")
                })
        
        return tools
    
    def _build_prompt(self, user_prompt: str, available_tools: Dict[str, Any]) -> str:
        """Build a simple, focused prompt for the AI"""
        
        # Format available tools for AI
        triggers_text = "\n".join([
            f"- {t['toolkit_slug']}.{t['trigger_slug']}: {t['name']}"
            for t in available_tools["triggers"][:10]  # Limit to avoid token bloat
        ])
        
        actions_text = "\n".join([
            f"- {a['toolkit_slug']}.{a['action_name']}: {a['name']}"
            for a in available_tools["actions"][:20]  # Limit to avoid token bloat
        ])
        
        return f"""You are a workflow automation expert. Create a workflow for: "{user_prompt}"

AVAILABLE TRIGGERS:
{triggers_text}

AVAILABLE ACTIONS:
{actions_text}

INSTRUCTIONS:
1. Use ONLY the triggers and actions listed above
2. Create a workflow with 1 trigger and 2-4 actions
3. Make it realistic and useful
4. Return ONLY valid JSON, no other text

EXAMPLE WORKFLOW:
{{
  "schema_type": "executable",
  "workflow": {{
    "name": "Email to Slack Notification",
    "description": "Send Slack notifications when new emails arrive",
    "triggers": [{{
      "toolkit_slug": "gmail",
      "composio_trigger_slug": "new_email"
    }}],
    "actions": [{{
      "toolkit_slug": "slack",
      "action_name": "send_message"
    }}]
  }},
  "connections": []
}}

Now create a workflow for "{user_prompt}" using the available tools above. Return ONLY the JSON."""
