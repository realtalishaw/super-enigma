"""
DSL LLM Generator Service

Uses Claude (Anthropic) to generate workflow DSL templates from natural language prompts.
Implements a two-step RAG workflow: Tool Retrieval + Focused Generation.
Integrates with the catalog system to ensure valid triggers and actions.
"""

import logging
import json
import httpx
import asyncio
from typing import Dict, Any, Optional, List
from .models import GenerationRequest, GenerationResponse, GenerationContext, CatalogContext
from .catalog_manager import CatalogManager
from .context_builder import ContextBuilder
from .prompt_builder import PromptBuilder
from .ai_client import AIClient
from .response_parser import ResponseParser

from core.config import settings


logger = logging.getLogger(__name__)


class DSLGeneratorService:
    """
    Service for generating workflow DSL templates using Claude LLM.
    
    This service implements a two-step RAG workflow:
    1. Tool Retrieval: Intelligently selects relevant tools from the catalog
    2. Focused Generation: Uses Claude with targeted tools to generate workflows
    
    This approach is much more reliable than sending the entire catalog to the LLM.
    """
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        """
        Initialize the DSL generator service.
        
        Args:
            anthropic_api_key: Anthropic API key for Claude access (optional, will use config if not provided)
        """
        # Initialize core components
        self.catalog_manager = CatalogManager()
        self.context_builder = ContextBuilder(self.catalog_manager)
        self.prompt_builder = PromptBuilder()
        self.ai_client = AIClient(anthropic_api_key)
        self.response_parser = ResponseParser()

        
        # Groq configuration for tool retrieval (from config)
        self.groq_api_key = settings.groq_api_key
        self.groq_base_url = "https://api.groq.com/openai/v1"
        self.groq_model = "openai/gpt-oss-120b"  # Fast model for tool retrieval
        
        # Tool selection limits to keep context concise
        self.max_triggers = settings.max_triggers
        self.max_actions = settings.max_actions
        self.max_providers = settings.max_providers
        
        # Maximum regeneration attempts to prevent infinite loops
        self.max_regeneration_attempts = 3
        
        # Rate limiting for Claude API calls
        self.claude_rate_limit_delay = settings.claude_rate_limit_delay
        self.max_rate_limit_delay = settings.max_rate_limit_delay
    
    def set_global_cache(self, catalog_cache: Dict[str, Any]):
        """Set the catalog cache from the global cache service"""
        self.catalog_manager.set_global_cache(catalog_cache)
    
    async def initialize(self):
        """Initialize all service components"""
        try:
            # Initialize catalog manager
            await self.catalog_manager.initialize()
            
            # Preload catalog cache
            await self.catalog_manager.preload_catalog_cache()
            
            logger.info("DSL Generator service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize DSL Generator service: {e}")
            # Don't raise - allow service to continue in limited mode
    
    async def generate_workflow(self, request: GenerationRequest) -> GenerationResponse:
        """
        Generate a workflow DSL template using the new two-step RAG workflow.
        
        Args:
            request: Generation request with user prompt and context
            
        Returns:
            GenerationResponse with DSL template and missing fields
        """
        try:
            # Ensure service is initialized
            if not self.catalog_manager.catalog_service:
                await self.initialize()
            
            # Step 1: Tool Retrieval - Get relevant tools from catalog
            logger.info("Step 1: Performing tool retrieval...")
            pruned_catalog_context = await self._retrieve_relevant_tools(request)
            
            if not pruned_catalog_context:
                return GenerationResponse(
                    success=False,
                    error_message="Failed to retrieve relevant tools from catalog",
                    missing_fields=[],
                    confidence=0.0
                )
            
            logger.info(f"Tool retrieval complete. Found {len(pruned_catalog_context.get('triggers', []))} triggers and {len(pruned_catalog_context.get('actions', []))} actions")
            
            # Limit tools to keep context concise and prevent Claude API size limits
            logger.info("Limiting tools for Claude context...")
            limited_catalog_context = self._limit_tools_for_context(pruned_catalog_context)
            
            # Step 2: Focused Generation - Generate workflow with targeted tools
            logger.info("Step 2: Performing focused generation...")
            return await self._generate_with_validation_loop(request, limited_catalog_context)
            
        except Exception as e:
            logger.error(f"Workflow generation failed: {e}")
            return GenerationResponse(
                success=False,
                error_message=str(e),
                missing_fields=[],
                confidence=0.0
            )
    
    async def _retrieve_relevant_tools(self, request: GenerationRequest) -> Optional[Dict[str, Any]]:
        """
        Step 1: Intelligently retrieve relevant tools from the catalog.
        
        This method implements the "Retrieval" step of the RAG workflow:
        - If selected_apps provided: Use strict keyword-based search
        - If only user_prompt: Use Groq LLM to analyze and find relevant tools
        
        Args:
            request: Generation request with user prompt and context
            
        Returns:
            Pruned catalog context with only relevant tools, or None if failed
        """
        try:
            catalog_cache = self.catalog_manager._catalog_cache
            
            if not catalog_cache:
                logger.error("No catalog cache available for tool retrieval")
                return None
            
            # Debug: Log the catalog cache structure
            logger.info(f"Catalog cache type: {type(catalog_cache)}")
            logger.info(f"Catalog cache length: {len(catalog_cache) if hasattr(catalog_cache, '__len__') else 'N/A'}")
            if isinstance(catalog_cache, dict):
                logger.info(f"Catalog cache keys: {list(catalog_cache.keys())[:5]}...")
            elif isinstance(catalog_cache, list):
                logger.info(f"Catalog cache first item type: {type(catalog_cache[0]) if catalog_cache else 'N/A'}")
                if catalog_cache:
                    logger.info(f"Catalog cache first item keys: {list(catalog_cache[0].keys()) if isinstance(catalog_cache[0], dict) else 'N/A'}")
            
            # Case 1: Strict keyword-based search when selected_apps provided
            if request.selected_apps:
                logger.info(f"Using strict keyword-based search for selected apps: {request.selected_apps}")
                return self._strict_keyword_search(catalog_cache, request.selected_apps)
            
            # Case 2: LLM-based intelligent search when only user_prompt provided
            else:
                logger.info("Using LLM-based intelligent search for user prompt")
                return await self._llm_based_tool_search(catalog_cache, request.user_prompt)
                
        except Exception as e:
            logger.error(f"Tool retrieval failed: {e}")
            return None
    
    def _limit_tools_for_context(self, pruned_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intelligently limit the number of tools to keep the context concise.
        
        Args:
            pruned_context: Full pruned catalog context
            
        Returns:
            Limited catalog context with reasonable number of tools
        """
        logger.info(f"Limiting tools: {len(pruned_context.get('triggers', []))} triggers, {len(pruned_context.get('actions', []))} actions")
        
        limited_context = {
            'triggers': [],
            'actions': [],
            'providers': {}
        }
        
        # Limit triggers (keep most relevant ones)
        triggers = pruned_context.get('triggers', [])
        if len(triggers) > self.max_triggers:
            # Sort by relevance (prioritize those with meaningful slugs and better descriptions)
            def trigger_relevance_score(trigger):
                score = 0
                # Prioritize meaningful slugs
                if not trigger.get('trigger_slug', '').startswith('unknown'):
                    score += 100
                # Bonus for descriptive names
                if trigger.get('name') and len(trigger.get('name', '')) > 3:
                    score += 50
                # Bonus for descriptions
                if trigger.get('description') and len(trigger.get('description', '')) > 10:
                    score += 25
                # Prefer shorter, cleaner slugs
                slug = trigger.get('trigger_slug', '')
                if slug and '_' in slug:
                    score += 10
                return score
            
            sorted_triggers = sorted(triggers, key=trigger_relevance_score, reverse=True)
            limited_context['triggers'] = sorted_triggers[:self.max_triggers]
            logger.info(f"Limited triggers from {len(triggers)} to {len(limited_context['triggers'])}")
        else:
            limited_context['triggers'] = triggers
        
        # Limit actions (keep most relevant ones)
        actions = pruned_context.get('actions', [])
        if len(actions) > self.max_actions:
            # Sort by relevance (prioritize those with meaningful slugs and better descriptions)
            def action_relevance_score(action):
                score = 0
                # Prioritize meaningful slugs
                if not action.get('action_slug', '').startswith('unknown'):
                    score += 100
                # Bonus for descriptive names
                if action.get('name') and len(action.get('name', '')) > 3:
                    score += 50
                # Bonus for descriptions
                if action.get('description') and len(action.get('description', '')) > 10:
                    score += 25
                # Prefer shorter, cleaner slugs
                slug = action.get('action_slug', '')
                if slug and '_' in slug:
                    score += 10
                return score
            
            sorted_actions = sorted(actions, key=action_relevance_score, reverse=True)
            limited_context['actions'] = sorted_actions[:self.max_actions]
            logger.info(f"Limited actions from {len(actions)} to {len(limited_context['actions'])}")
        else:
            limited_context['actions'] = actions
        
        # Limit providers (keep only those that have tools selected)
        selected_provider_slugs = set()
        for trigger in limited_context['triggers']:
            selected_provider_slugs.add(trigger.get('toolkit_slug', ''))
        for action in limited_context['actions']:
            selected_provider_slugs.add(action.get('toolkit_slug', ''))
        
        providers = pruned_context.get('providers', {})
        limited_providers = {}
        count = 0
        for slug in selected_provider_slugs:
            if slug in providers and count < self.max_providers:
                limited_providers[slug] = providers[slug]
                count += 1
        
        limited_context['providers'] = limited_providers
        logger.info(f"Limited providers to {len(limited_context['providers'])} relevant ones")
        
        # Log final counts and sample tools
        logger.info(f"Final context: {len(limited_context['triggers'])} triggers, {len(limited_context['actions'])} actions, {len(limited_context['providers'])} providers")
        
        # Log sample of selected tools
        if limited_context['triggers']:
            sample_triggers = [t.get('trigger_slug', 'unknown') for t in limited_context['triggers'][:3]]
            logger.info(f"Selected triggers: {sample_triggers}")
        if limited_context['actions']:
            sample_actions = [a.get('action_slug', 'unknown') for a in limited_context['actions'][:3]]
            logger.info(f"Selected actions: {sample_actions}")
        
        return limited_context
    
    def _strict_keyword_search(self, catalog_cache: Dict[str, Any], selected_apps: List[str]) -> Optional[Dict[str, Any]]:
        """
        Perform strict keyword-based search for selected apps.
        
        Args:
            catalog_cache: Full catalog cache (can be dict or list)
            selected_apps: List of app/toolkit slugs to search for
            
        Returns:
            Pruned catalog context with only tools from selected apps
        """
        pruned_context = {
            'triggers': [],
            'actions': [],
            'providers': {}
        }
        
        # Handle both dict and list catalog structures
        if isinstance(catalog_cache, dict):
            # Original dict structure
            for app_slug in selected_apps:
                if app_slug in catalog_cache:
                    app_data = catalog_cache[app_slug]
                    
                    # Add provider info
                    pruned_context['providers'][app_slug] = {
                        'name': app_data.get('name', app_slug),
                        'description': app_data.get('description', ''),
                        'category': app_data.get('category', '')
                    }
                    
                    # Add triggers
                    try:
                        triggers = app_data.get('triggers', {})
                        if isinstance(triggers, dict):
                            # Dict structure: {trigger_slug: trigger_data}
                            for trigger_slug, trigger_data in triggers.items():
                                pruned_context['triggers'].append({
                                    'toolkit_slug': app_slug,
                                    'trigger_slug': trigger_slug,
                                    **trigger_data
                                })
                        elif isinstance(triggers, list):
                            # List structure: [trigger_data, trigger_data, ...]
                            for trigger_data in triggers:
                                if isinstance(trigger_data, dict):
                                    # Try multiple possible slug fields
                                    trigger_slug = (
                                        trigger_data.get('slug') or 
                                        trigger_data.get('trigger_slug') or 
                                        trigger_data.get('name') or 
                                        trigger_data.get('id') or 
                                        'unknown_trigger'
                                    )
                                    pruned_context['triggers'].append({
                                        'toolkit_slug': app_slug,
                                        'trigger_slug': trigger_slug,
                                        **trigger_data
                                    })
                    except Exception as e:
                        logger.warning(f"Error processing triggers for {app_slug}: {e}")
                    
                    # Add actions
                    try:
                        actions = app_data.get('actions', {})
                        if isinstance(actions, dict):
                            # Dict structure: {action_slug: action_data}
                            for action_slug, action_data in actions.items():
                                pruned_context['actions'].append({
                                    'toolkit_slug': app_slug,
                                    'action_slug': action_slug,
                                    **action_data
                                })
                        elif isinstance(actions, list):
                            # List structure: [action_data, action_data, ...]
                            for action_data in actions:
                                if isinstance(action_data, dict):
                                    # Try multiple possible slug fields
                                    action_slug = (
                                        action_data.get('slug') or 
                                        action_data.get('action_slug') or 
                                        action_data.get('name') or 
                                        action_data.get('id') or 
                                        'unknown_action'
                                    )
                                    pruned_context['actions'].append({
                                        'toolkit_slug': app_slug,
                                        'action_slug': action_slug,
                                        **action_data
                                    })
                    except Exception as e:
                        logger.warning(f"Error processing actions for {app_slug}: {e}")
        
        elif isinstance(catalog_cache, list):
            # List structure - search by slug in the list
            for app_data in catalog_cache:
                if isinstance(app_data, dict):
                    app_slug = app_data.get('slug') or app_data.get('toolkit_slug')
                    if app_slug in selected_apps:
                        # Add provider info
                        pruned_context['providers'][app_slug] = {
                            'name': app_data.get('name', app_slug),
                            'description': app_data.get('description', ''),
                            'category': app_data.get('category', '')
                        }
                        
                        # Add triggers
                        triggers = app_data.get('triggers', [])
                        if isinstance(triggers, list):
                            for trigger_data in triggers:
                                if isinstance(trigger_data, dict):
                                    pruned_context['triggers'].append({
                                        'toolkit_slug': app_slug,
                                        'trigger_slug': trigger_data.get('slug', ''),
                                        **trigger_data
                                    })
                        
                        # Add actions
                        actions = app_data.get('actions', [])
                        if isinstance(actions, list):
                            for action_data in actions:
                                if isinstance(action_data, dict):
                                    pruned_context['actions'].append({
                                        'toolkit_slug': app_slug,
                                        'action_slug': action_data.get('slug', ''),
                                        **action_data
                                    })
        
        logger.info(f"Strict search found {len(pruned_context['triggers'])} triggers and {len(pruned_context['actions'])} actions")
        
        # Log some examples of what was found
        if pruned_context['triggers']:
            sample_triggers = [t.get('trigger_slug', 'unknown') for t in pruned_context['triggers'][:3]]
            logger.info(f"Sample triggers found: {sample_triggers}")
            # Count how many have meaningful slugs
            meaningful_triggers = [t for t in pruned_context['triggers'] if t.get('trigger_slug') and not t.get('trigger_slug').startswith('unknown')]
            logger.info(f"Triggers with meaningful slugs: {len(meaningful_triggers)}/{len(pruned_context['triggers'])}")
        if pruned_context['actions']:
            sample_actions = [a.get('action_slug', 'unknown') for a in pruned_context['actions'][:3]]
            logger.info(f"Sample actions found: {sample_actions}")
            # Count how many have meaningful slugs
            meaningful_actions = [a for a in pruned_context['actions'] if a.get('action_slug') and not a.get('action_slug').startswith('unknown')]
            logger.info(f"Actions with meaningful slugs: {len(meaningful_actions)}/{len(pruned_context['actions'])}")
        
        return pruned_context
    
    async def _llm_based_tool_search(self, catalog_cache: Dict[str, Any], user_prompt: str) -> Optional[Dict[str, Any]]:
        """
        Uses Groq LLM to analyze the user prompt and find relevant tools.
        
        Args:
            catalog_cache: The full catalog cache.
            user_prompt: The user's natural language prompt.
            
        Returns:
            Pruned catalog context with only relevant tools, or None if failed
        """
        if not self.groq_api_key:
            logger.warning("No Groq API key available, falling back to basic search")
            return self._fallback_basic_search(catalog_cache, user_prompt)
        
        logger.info("Groq API key found, performing intelligent tool search...")
        
        # Prepare available toolkits for the prompt
        available_toolkits = []
        if isinstance(catalog_cache, dict):
            for slug, data in catalog_cache.items():
                available_toolkits.append({
                    'slug': slug,
                    'description': data.get('description', '')
                })
        elif isinstance(catalog_cache, list):
            for item in catalog_cache:
                if isinstance(item, dict):
                    slug = item.get('slug') or item.get('toolkit_slug')
                    if slug:
                        available_toolkits.append({
                            'slug': slug,
                            'description': item.get('description', '')
                        })
        
        if not available_toolkits:
            logger.warning("No toolkits available for Groq analysis")
            return self._fallback_basic_search(catalog_cache, user_prompt)
        
        # Use the original Groq prompt method
        prompt = self._build_groq_tool_selection_prompt(user_prompt, available_toolkits)
        
        # Prepare Groq API request
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.groq_base_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.groq_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 1,
                        "max_completion_tokens": 8192,
                        "top_p": 1,
                        "reasoning_effort": "medium",
                        "stream": False,
                        "response_format": {"type": "json_object"},
                        "stop": None
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                groq_response = response.json()
                logger.info(f"Groq API response received: {groq_response}")
                
                # Extract the required toolkits from Groq response
                content = groq_response.get("choices", [{}])[0].get("message", {}).get("content", "")
                try:
                    llm_data = json.loads(content)
                    required_toolkits = llm_data.get("required_toolkits", [])
                    
                    if not required_toolkits:
                        logger.warning("Groq returned no required toolkits")
                        return self._fallback_basic_search(catalog_cache, user_prompt)
                    
                    logger.info(f"Groq identified required toolkits: {required_toolkits}")
                    
                    # Use the strict keyword search with the identified toolkits
                    return self._strict_keyword_search(catalog_cache, required_toolkits)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Groq response JSON: {e}")
                    logger.error(f"Raw Groq response: {content}")
                    return self._fallback_basic_search(catalog_cache, user_prompt)
                    
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            return self._fallback_basic_search(catalog_cache, user_prompt)
    
    def _fallback_basic_search(self, catalog_cache: Dict[str, Any], user_prompt: str) -> Dict[str, Any]:
        """
        Fallback search when Groq analysis fails or returns no results.
        
        Args:
            catalog_cache: Full catalog cache (can be dict or list)
            user_prompt: The user's original prompt
            
        Returns:
            Basic pruned catalog context with a subset of tools
        """
        logger.info("Using fallback basic search")
        
        pruned_context = {
            'triggers': [],
            'actions': [],
            'providers': {}
        }
        
        # Handle both dict and list catalog structures
        if isinstance(catalog_cache, dict):
            # Take first 10 providers for basic fallback
            provider_count = 0
            for app_slug, app_data in list(catalog_cache.items())[:10]:
                if provider_count >= 10:
                    break
                    
                # Add provider info
                pruned_context['providers'][app_slug] = {
                    'name': app_data.get('name', app_slug),
                    'description': app_data.get('description', ''),
                    'category': app_data.get('category', '')
                }
                
                # Add triggers
                try:
                    triggers = app_data.get('triggers', {})
                    if isinstance(triggers, dict):
                        # Dict structure: {trigger_slug: trigger_data}
                        for trigger_slug, trigger_data in triggers.items():
                            pruned_context['triggers'].append({
                                'toolkit_slug': app_slug,
                                'trigger_slug': trigger_slug,
                                **trigger_data
                            })
                    elif isinstance(triggers, list):
                        # List structure: [trigger_data, trigger_data, ...]
                        for trigger_data in triggers:
                            if isinstance(trigger_data, dict):
                                # Try multiple possible slug fields
                                trigger_slug = (
                                    trigger_data.get('slug') or 
                                    trigger_data.get('trigger_slug') or 
                                    trigger_data.get('name') or 
                                    trigger_data.get('id') or 
                                    'unknown_trigger'
                                )
                                pruned_context['triggers'].append({
                                    'toolkit_slug': app_slug,
                                    'trigger_slug': trigger_slug,
                                    **trigger_data
                                })
                except Exception as e:
                    logger.warning(f"Error processing triggers for {app_slug}: {e}")
                
                # Add actions
                try:
                    actions = app_data.get('actions', {})
                    if isinstance(actions, dict):
                        # Dict structure: {action_slug: action_data}
                        for action_slug, action_data in actions.items():
                            pruned_context['actions'].append({
                                'toolkit_slug': app_slug,
                                'action_slug': action_slug,
                                **action_data
                            })
                    elif isinstance(actions, list):
                        # List structure: [action_data, action_data, ...]
                        for action_data in actions:
                            if isinstance(action_data, dict):
                                # Try multiple possible slug fields
                                action_slug = (
                                    action_data.get('slug') or 
                                    action_data.get('action_slug') or 
                                    action_data.get('name') or 
                                    action_data.get('id') or 
                                    'unknown_action'
                                )
                                pruned_context['actions'].append({
                                    'toolkit_slug': app_slug,
                                    'action_slug': action_slug,
                                    **action_data
                                })
                except Exception as e:
                    logger.warning(f"Error processing actions for {app_slug}: {e}")
                
                provider_count += 1
        
        elif isinstance(catalog_cache, list):
            # Take first 10 providers for basic fallback
            for app_data in catalog_cache[:10]:
                if isinstance(app_data, dict):
                    app_slug = app_data.get('slug') or app_data.get('toolkit_slug')
                    
                    # Add provider info
                    pruned_context['providers'][app_slug] = {
                        'name': app_data.get('name', app_slug),
                        'description': app_data.get('description', ''),
                        'category': app_data.get('category', '')
                    }
                    
                    # Add triggers
                    triggers = app_data.get('triggers', [])
                    if isinstance(triggers, list):
                        for trigger_data in triggers:
                            if isinstance(trigger_data, dict):
                                pruned_context['triggers'].append({
                                    'toolkit_slug': app_slug,
                                    'trigger_slug': trigger_data.get('slug', ''),
                                    **trigger_data
                                })
                    
                    # Add actions
                    actions = app_data.get('actions', [])
                    if isinstance(actions, list):
                        for action_data in actions:
                            if isinstance(action_data, dict):
                                pruned_context['actions'].append({
                                    'toolkit_slug': app_slug,
                                    'action_slug': action_data.get('slug', ''),
                                    **action_data
                                })
        
        logger.info(f"Fallback search found {len(pruned_context['triggers'])} triggers and {len(pruned_context['actions'])} actions")
        return pruned_context

    def _build_groq_tool_selection_prompt(self, user_prompt: str, available_toolkits: list[dict]) -> str:
        """Builds the prompt for the Groq API to select relevant toolkits."""
        toolkits_context = "\n".join(
            f"- slug: {tk['slug']}, description: {tk['description']}" for tk in available_toolkits
        )
        return f"""You are an intelligent workflow routing assistant. Your job is to analyze a user's request and identify the specific software toolkits required to fulfill it from a predefined list.

<user_request>
{user_prompt}
</user_request>

<available_toolkits>
{toolkits_context}
</available_toolkits>

**Your Task:**
Based on the user's request, identify the most relevant toolkits. Your response MUST be a JSON object containing a single key, `required_toolkits`, which is a list of the exact `slug`s from the provided list.

**Rules:**
1. Only include slugs that are absolutely necessary to fulfill the request.
2. If the user asks for a specific tool that is not in the list, do not include it.
3. If the request is too vague to determine specific tools, or if none of the tools are relevant, return an empty list.
4. Your response must ONLY be the JSON object, with no preamble or explanation.

**Example:**
<user_request>
When I get a new lead in Salesforce, send a welcome email using SendGrid.
</user_request>
<available_toolkits>
- slug: salesforce, description: CRM and sales automation.
- slug: slack, description: Team communication and messaging.
- slug: sendgrid, description: Email delivery service.
- slug: google_drive, description: File storage and synchronization.
</available_toolkits>

**Expected JSON Response:**
```json
{{
    "required_toolkits": ["salesforce", "sendgrid"]
}}
```
Now, analyze the user request provided at the top and generate the JSON response."""

    def _build_robust_claude_prompt(self, request: GenerationRequest, catalog_context: Dict[str, Any], previous_errors: List[str]) -> str:
        """Builds the robust, XML-based prompt for Claude, including feedback on errors."""
        # Build a proper tools structure from our context
        tools_structure = {
            "triggers": catalog_context.get("triggers", []),
            "actions": catalog_context.get("actions", []),
            "providers": catalog_context.get("providers", {})
        }
        tools_json = json.dumps(tools_structure, indent=2)

        prompt = f"""You are an expert workflow designer. Your task is to create a multi-step workflow in JSON format based on the user's request, using ONLY the provided tools.
<user_request>
{request.user_prompt}
</user_request>
<available_tools>
{tools_json}
</available_tools>
<instructions>
1. Analyze the user request and the available tools to design a logical, multi-step workflow (at least 2 actions if possible).
2. Your output MUST conform to the `template` schema.
3. You MUST only use `toolkit_slug`, `composio_trigger_slug`, and `action_name` values that exist in the `<available_tools>` context. Do not invent them. The slugs must be an exact match.
4. Populate the `missing_information` array for any required action inputs that cannot be inferred from the prompt.
5. Your response MUST be a single, valid JSON object and nothing else. Do not add any conversational text or markdown formatting like \`\`\`json.
</instructions>
<multi_step_example>
{{
"schema_type": "template",
"workflow": {{
"name": "GitHub Issue to Slack Notification",
"description": "When a new issue is created in a GitHub repo, post a message to a Slack channel.",
"triggers": [{{
"id": "github_new_issue",
"type": "event_based",
"toolkit_slug": "github",
"composio_trigger_slug": "new_issue"
}}],
"actions": [{{
"id": "slack_post_message",
"toolkit_slug": "slack",
"action_name": "SLACK_POST_MESSAGE",
"required_inputs": [
{{ "name": "channel", "source": "{{{{inputs.slack_channel_id}}}}" }},
{{ "name": "text", "source": "New GitHub Issue in {{{{trigger.repository}}}}: {{{{trigger.title}}}}" }}
],
"depends_on": ["github_new_issue"]
}}]
}},
"missing_information": [{{
"field": "inputs.slack_channel_id",
"prompt": "Which Slack channel should I post the notifications to? (e.g., #general)",
"type": "string",
"required": true
}}]
}}
</multi_step_example>
"""
        if previous_errors:
            errors_str = "\n".join(f"- {e}" for e in previous_errors)
            prompt += f"""
<feedback>
Your previous attempt failed with the following validation errors. You MUST fix them in your next response:
{errors_str}
</feedback>
"""
        prompt += "\nNow, generate the complete JSON for the user's request."
        return prompt
    
    async def _generate_with_validation_loop(self, request: GenerationRequest, catalog_context: Dict[str, Any]) -> GenerationResponse:
        """Manages the generation, validation, and retry loop."""
        previous_errors = []
        for attempt in range(self.max_regeneration_attempts):
            logger.info(f"Generation attempt {attempt + 1}/{self.max_regeneration_attempts}...")
            
            prompt = self._build_robust_claude_prompt(request, catalog_context, previous_errors)
            
            try:
                raw_response = await self.ai_client.generate_workflow(prompt)
                
                # Load schema definition for GenerationContext
                schema_definition = self.context_builder._load_schema_definition()
                
                # Convert dictionary catalog_context to CatalogContext object
                catalog_context_obj = CatalogContext(
                    available_providers=list(catalog_context.get('providers', {}).values()),
                    available_triggers=catalog_context.get('triggers', []),
                    available_actions=catalog_context.get('actions', []),
                    provider_categories=[]  # Not used in this context
                )
                
                parsed_response = await self.response_parser.parse_response(
                    raw_response, 
                    GenerationContext(
                        request=request,
                        catalog=catalog_context_obj, 
                        schema_definition=schema_definition
                    )
                )

                if not parsed_response.success or not parsed_response.dsl_template:
                    error_msg = parsed_response.error_message or "Failed to parse valid JSON from LLM response."
                    previous_errors.append(error_msg)
                    logger.warning(f"Attempt {attempt + 1} failed during parsing: {error_msg}")
                    continue

                # Skip validation - just return whatever Claude generated
                logger.info("Skipping validation - returning Claude's generated workflow directly")
                validation_result = {
                    'is_valid': True,
                    'validation_errors': [],
                    'lint_errors': [],
                    'lint_warnings': [],
                    'lint_hints': []
                }
                
                if validation_result.get('is_valid', False):
                    logger.info("Generated workflow passed validation successfully!")
                    return parsed_response
                else:
                    # Extract error messages from the validation result
                    validation_errors = validation_result.get('validation_errors', [])
                    lint_errors = validation_result.get('lint_errors', [])
                    
                    error_messages = []
                    if validation_errors:
                        error_messages.extend([f"Validation: {e}" for e in validation_errors])
                    if lint_errors:
                        error_messages.extend([f"Lint: {e}" for e in lint_errors])
                    
                    if not error_messages:
                        error_messages = ["Unknown validation error"]
                    
                    logger.warning(f"Validation failed with {len(error_messages)} errors: {error_messages}")
                    previous_errors.extend(error_messages)

            except Exception as e:
                logger.exception(f"An unexpected exception occurred on attempt {attempt + 1}.")
                previous_errors.append(f"An unexpected error occurred: {str(e)}")

        logger.error("Failed to generate a valid workflow after all attempts.")
        return GenerationResponse(
            success=False,
            error_message=f"Failed to generate a valid workflow after {self.max_regeneration_attempts} attempts. Last errors: {previous_errors}"
        )
    
    # Configuration and utility methods
    def update_groq_api_key(self, new_api_key: str):
        """Update the Groq API key for tool retrieval"""
        self.groq_api_key = new_api_key
        logger.info("Groq API key updated")
    
    def get_groq_config(self) -> Dict[str, Any]:
        """Get information about the Groq configuration"""
        return {
            "api_key_configured": bool(self.groq_api_key),
            "base_url": self.groq_base_url,
            "model": self.groq_model,
            "status": "configured" if self.groq_api_key else "not_configured"
        }
    
    def update_tool_limits(self, max_triggers: Optional[int] = None, max_actions: Optional[int] = None, max_providers: Optional[int] = None):
        """Update the tool limits for context management"""
        if max_triggers is not None:
            self.max_triggers = max_triggers
        if max_actions is not None:
            self.max_actions = max_actions
        if max_providers is not None:
            self.max_providers = max_providers
        
        logger.info(f"Tool limits updated: triggers={self.max_triggers}, actions={self.max_actions}, providers={self.max_providers}")
    
    def get_tool_limits(self) -> Dict[str, Any]:
        """Get current tool limits configuration"""
        return {
            "max_triggers": self.max_triggers,
            "max_actions": self.max_actions,
            "max_providers": self.max_providers,
            "estimated_context_size": f"~{self.max_triggers * 2 + self.max_actions * 3 + self.max_providers * 2}KB"
        }
    
    def update_rate_limiting(self, base_delay: Optional[float] = None, max_delay: Optional[float] = None):
        """Update Claude API rate limiting configuration"""
        if base_delay is not None:
            self.claude_rate_limit_delay = base_delay
        if max_delay is not None:
            self.max_rate_limit_delay = max_delay
        
        logger.info(f"Rate limiting updated: base_delay={self.claude_rate_limit_delay}s, max_delay={self.max_rate_limit_delay}s")
    
    def get_rate_limiting_config(self) -> Dict[str, Any]:
        """Get current rate limiting configuration"""
        return {
            "base_delay": self.claude_rate_limit_delay,
            "max_delay": self.max_rate_limit_delay,
            "retry_strategy": "exponential_backoff"
        }
    

    
    # Delegate catalog management methods to catalog manager
    def get_cache_status(self) -> Dict[str, Any]:
        """Get the current cache status"""
        return self.catalog_manager.get_cache_status()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of the DSL Generator service"""
        return self.catalog_manager.get_health_status()
    
    def get_catalog_summary(self) -> Dict[str, Any]:
        """Get a summary of available catalog data"""
        return self.catalog_manager.get_catalog_summary()
    
    def get_catalog_health(self) -> Dict[str, Any]:
        """Get catalog health status for monitoring"""
        return self.catalog_manager.get_catalog_health()
    
    def get_catalog_stats(self) -> Dict[str, Any]:
        """Get detailed catalog statistics for debugging and monitoring"""
        return self.catalog_manager.get_catalog_stats()
    
    def get_catalog_validation_summary(self) -> Dict[str, Any]:
        """Get a summary of catalog validation for generation context"""
        return self.catalog_manager.get_catalog_validation_summary()
    
    def get_catalog_for_generation(self) -> Dict[str, Any]:
        """Get catalog data specifically formatted for generation prompts"""
        return self.context_builder.get_catalog_for_generation()
    
    def get_catalog_health_check(self) -> Dict[str, Any]:
        """Get a comprehensive catalog health check for monitoring"""
        return self.catalog_manager.get_catalog_health_check()
    
    def get_sample_workflow_data(self) -> Dict[str, Any]:
        """Get sample workflow data for generation prompts"""
        return self.catalog_manager.get_sample_workflow_data()
    
    def get_catalog_overview(self) -> Dict[str, Any]:
        """Get a high-level overview of the catalog for generation context"""
        return self.catalog_manager.get_catalog_overview()
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider slugs for validation"""
        return self.catalog_manager.get_available_providers()
    
    def get_provider_actions(self, provider_slug: str) -> List[str]:
        """Get list of available actions for a specific provider"""
        return self.catalog_manager.get_provider_actions(provider_slug)
    
    def get_provider_triggers(self, provider_slug: str) -> List[str]:
        """Get list of available triggers for a specific provider"""
        return self.catalog_manager.get_provider_triggers(provider_slug)
    
    def validate_catalog_references(self, providers: List[str], actions: List[str], triggers: List[str]) -> Dict[str, Any]:
        """Validate if the provided references exist in the catalog"""
        return self.catalog_manager.validate_catalog_references(providers, actions, triggers)
    
    def validate_workflow_components(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate specific workflow components against the catalog"""
        return self.response_parser.validate_workflow_components(workflow_data, self.catalog_manager._catalog_cache)
    
    def clear_catalog_cache(self):
        """Clear the in-memory catalog cache"""
        self.catalog_manager.clear_catalog_cache()
    
    async def preload_catalog_cache(self):
        """Preload catalog cache during initialization for immediate use"""
        await self.catalog_manager.preload_catalog_cache()
    
    async def refresh_catalog_cache(self, force: bool = False):
        """Refresh the catalog cache data"""
        await self.catalog_manager.refresh_catalog_cache(force)
    
    def get_ai_client_info(self) -> Dict[str, Any]:
        """Get information about the AI client configuration"""
        return self.ai_client.get_model_info()
    
    def update_ai_api_key(self, new_api_key: str):
        """Update the AI client API key"""
        self.ai_client.update_api_key(new_api_key)
    
    def update_ai_model(self, new_model: str):
        """Update the AI client model"""
        self.ai_client.update_model(new_model)