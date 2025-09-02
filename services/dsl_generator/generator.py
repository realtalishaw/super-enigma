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
from .workflow_validator import WorkflowValidator

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
        self.workflow_validator = WorkflowValidator()

        
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

    async def generate_multiple_workflows(self, request: GenerationRequest, num_workflows: int = 1) -> List[GenerationResponse]:
        """
        Generate multiple workflow DSL templates in parallel.
        
        Args:
            request: Generation request with user prompt and context
            num_workflows: Number of workflows to generate (1-5)
            
        Returns:
            List of GenerationResponse objects
        """
        if num_workflows < 1 or num_workflows > 5:
            raise ValueError("num_workflows must be between 1 and 5")
        
        if num_workflows == 1:
            # Single generation - use the existing method
            response = await self.generate_workflow(request)
            return [response]
        
        logger.info(f"Generating {num_workflows} workflows in parallel...")
        
        # Create tasks for parallel generation
        tasks = []
        for i in range(num_workflows):
            # Create a slightly modified request for each generation to add variety
            modified_request = GenerationRequest(
                user_prompt=request.user_prompt,
                selected_apps=request.selected_apps,
                user_id=request.user_id,
                workflow_type=request.workflow_type,
                complexity=request.complexity
            )
            
            # Add a small variation to the prompt to encourage diversity
            if i > 0:
                modified_request.user_prompt = f"{request.user_prompt} (variation {i+1})"
            
            task = self.generate_workflow(modified_request)
            tasks.append(task)
        
        # Execute all generations in parallel
        try:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and handle any exceptions
            processed_responses = []
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    logger.warning(f"Generation {i+1} failed: {response}")
                    # Create a fallback response for failed generations
                    fallback_response = GenerationResponse(
                        success=False,
                        error_message=f"Generation failed: {str(response)}",
                        missing_fields=[],
                        confidence=0.0
                    )
                    processed_responses.append(fallback_response)
                else:
                    processed_responses.append(response)
            
            logger.info(f"Successfully generated {len(processed_responses)} workflows")
            return processed_responses
            
        except Exception as e:
            logger.error(f"Parallel workflow generation failed: {e}")
            # Fallback to single generation
            fallback_response = await self.generate_workflow(request)
            return [fallback_response]
    
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
                                    # Use the slug field from database
                                    trigger_slug = trigger_data.get('slug') or 'unknown_trigger'
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
                                    # Use the slug field from database
                                    action_slug = action_data.get('slug') or 'unknown_action'
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
                                        **action_data,  # Spread the original data first
                                        'toolkit_slug': app_slug,
                                        'action_slug': action_data.get('slug', '')  # Override with the slug last
                                    })
        
        logger.info(f"Strict search found {len(pruned_context['triggers'])} triggers and {len(pruned_context['actions'])} actions")
        
        # Log some examples of what was found
        if pruned_context['triggers']:
            sample_triggers = [t.get('trigger_slug', 'unknown') for t in pruned_context['triggers'][:3]]
            logger.info(f"Sample triggers found: {sample_triggers}")
            # Count how many have meaningful slugs
            meaningful_triggers = [t for t in pruned_context['triggers'] if t.get('trigger_slug') and not t.get('trigger_slug').startswith('unknown')]
            logger.info(f"Triggers with meaningful slugs: {len(meaningful_triggers)}/{len(pruned_context['triggers'])}")
            
            # Log any triggers missing slugs
            missing_slug_triggers = [t for t in pruned_context['triggers'] if not t.get('trigger_slug')]
            if missing_slug_triggers:
                logger.warning(f"Found {len(missing_slug_triggers)} triggers without trigger_slug")
                for trigger in missing_slug_triggers[:3]:
                    logger.warning(f"  Trigger: {trigger.get('name')} - missing trigger_slug")
                    
        if pruned_context['actions']:
            sample_actions = [a.get('action_slug', 'unknown') for a in pruned_context['actions'][:3]]
            logger.info(f"Sample actions found: {sample_actions}")
            # Count how many have meaningful slugs
            meaningful_actions = [a for a in pruned_context['actions'] if a.get('action_slug') and not a.get('action_slug').startswith('unknown')]
            logger.info(f"Actions with meaningful slugs: {len(meaningful_actions)}/{len(pruned_context['actions'])}")
            
            # Log any actions missing slugs
            missing_slug_actions = [a for a in pruned_context['actions'] if not a.get('action_slug')]
            if missing_slug_actions:
                logger.warning(f"Found {len(missing_slug_actions)} actions without action_slug")
                for action in missing_slug_actions[:3]:
                    logger.warning(f"  Action: {action.get('name')} - missing action_slug")
        
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
        """
        Builds a sophisticated prompt for Groq to pre-plan the workflow by selecting
        the exact trigger and action slugs.
        """
        
        # --- IMPROVEMENT: Format the full tool list for the LLM ---
        # This gives the LLM the necessary context to choose specific, valid tools.
        tool_context_str = ""
        for toolkit in available_toolkits:
            tool_context_str += f"\n- Toolkit: {toolkit['slug']}\n"
            tool_context_str += f"  Description: {toolkit['description']}\n"
            
            # Get triggers from the full catalog cache, not just the summary
            full_toolkit_data = self._catalog_cache.get("toolkits", {}).get(toolkit['slug'], {})
            
            triggers = full_toolkit_data.get("triggers", [])
            if triggers:
                tool_context_str += "  Triggers:\n"
                for t in triggers:
                    slug = t.get('slug') or t.get('name')
                    desc = t.get('description', 'No description.')
                    tool_context_str += f"    - slug: \"{slug}\", description: \"{desc}\"\n"
            
            actions = full_toolkit_data.get("actions", [])
            if actions:
                tool_context_str += "  Actions:\n"
                for a in actions:
                    slug = a.get('slug') or a.get('name')
                    desc = a.get('description', 'No description.')
                    tool_context_str += f"    - slug: \"{slug}\", description: \"{desc}\"\n"

        prompt = f"""You are an expert workflow architect. Your job is to analyze a user's request and design a logical sequence of operations by selecting ONE trigger and one or more actions from a comprehensive catalog of available tools.

<user_request>
{user_prompt}
</user_request>

<available_tools>
{tool_context_str}
</available_tools>

**Your Task:**
1.  **Reasoning:** First, think step-by-step about how to accomplish the user's goal with the available tools.
2.  **Tool Selection:** Based on your reasoning, select exactly ONE trigger and a sequence of one or more actions.
3.  **JSON Output:** Your response MUST be a JSON object with three keys: "reasoning", "trigger_slug", and "action_slugs".

**Rules for Tool Selection:**
- The slugs in your response MUST be an EXACT match to a slug from the `<available_tools>` list.
- If a suitable workflow cannot be built, return `null` for `trigger_slug` and an empty list for `action_slugs`.

**Example:**
<user_request>
When I get a new lead in Salesforce, add them to a Google Sheet and send a celebration message in Slack.
</user_request>

**Expected JSON Response:**
```json
{{
    "reasoning": "The workflow starts when a new lead is created in Salesforce. Then, it adds a new row to a Google Sheet with the lead's information. Finally, it posts a message to a Slack channel to announce the new lead.",
    "trigger_slug": "SALESFORCE_NEW_LEAD_TRIGGER",
    "action_slugs": ["GOOGLESHEETS_CREATE_SPREADSHEET_ROW", "SLACK_SEND_MESSAGE"]
}}
```

Now, analyze the user request provided at the top and generate the JSON response."""

    def _validate_generated_workflow(self, workflow_data: Dict[str, Any], catalog_context: Dict[str, Any]) -> List[str]:
        """Validate the generated workflow against the available tools and schema requirements."""
        errors = []
        
        # Create toolkit mapping for validation
        toolkit_mapping = self._create_toolkit_mapping(catalog_context)
        
        # Validate triggers
        if "triggers" in workflow_data.get("workflow", {}):
            for trigger in workflow_data["workflow"]["triggers"]:
                toolkit_slug = trigger.get("toolkit_slug")
                trigger_slug = trigger.get("composio_trigger_slug")
                
                if not toolkit_slug:
                    errors.append("Missing toolkit_slug in trigger")
                elif toolkit_slug not in toolkit_mapping:
                    errors.append(f"Unknown toolkit: {toolkit_slug}")
                elif trigger_slug:
                    if toolkit_slug in toolkit_mapping and "triggers" in toolkit_mapping[toolkit_slug]:
                        if trigger_slug not in toolkit_mapping[toolkit_slug]["triggers"]:
                            errors.append(f"Unknown trigger '{trigger_slug}' in toolkit '{toolkit_slug}'")
                    else:
                        errors.append(f"Toolkit '{toolkit_slug}' has no triggers")
        
        # Validate actions
        if "actions" in workflow_data.get("workflow", {}):
            for action in workflow_data["workflow"]["actions"]:
                toolkit_slug = action.get("toolkit_slug")
                action_name = action.get("action_name")
                
                if not toolkit_slug:
                    errors.append("Missing toolkit_slug in action")
                elif toolkit_slug not in toolkit_mapping:
                    errors.append(f"Unknown toolkit: {toolkit_slug}")
                elif action_name:
                    if toolkit_slug in toolkit_mapping and "actions" in toolkit_mapping[toolkit_slug]:
                        if action_name not in toolkit_mapping[toolkit_slug]["actions"]:
                            errors.append(f"Unknown action '{action_name}' in toolkit '{toolkit_slug}'")
                    else:
                        errors.append(f"Toolkit '{toolkit_slug}' has no actions")
                
                # Validate required_inputs
                required_inputs = action.get("required_inputs", [])
                if isinstance(required_inputs, list):
                    for input_param in required_inputs:
                        if not isinstance(input_param, dict):
                            errors.append(f"Invalid required_inputs format in action {action.get('id', 'unknown')}")
                            continue
                        
                        if "name" not in input_param:
                            errors.append(f"Missing 'name' in required_inputs for action {action.get('id', 'unknown')}")
                        if "source" not in input_param:
                            errors.append(f"Missing 'source' in required_inputs for action {action.get('id', 'unknown')}")
                        if "type" not in input_param:
                            errors.append(f"Missing 'type' in required_inputs for action {action.get('id', 'unknown')}")
                        else:
                            valid_types = ["string", "number", "boolean", "array"]
                            if input_param["type"] not in valid_types:
                                errors.append(f"Invalid type '{input_param['type']}' in required_inputs. Must be one of: {valid_types}")
        
        return errors

    def _create_toolkit_mapping(self, catalog_context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Create a comprehensive mapping of available toolkits, triggers, and actions."""
        toolkit_mapping = {}
        
        for slug, data in catalog_context.get("toolkits", {}).items():
            toolkit_mapping[slug] = {
                "name": data.get("name", slug),
                "description": data.get("description", ""),
                "triggers": {},
                "actions": {}
            }
            
            # Map triggers
            for trigger in data.get("triggers", []):
                trigger_slug = trigger.get('slug') or trigger.get('name')
                if trigger_slug:
                    toolkit_mapping[slug]["triggers"][trigger_slug] = {
                        "name": trigger.get('name', trigger_slug),
                        "description": trigger.get('description', ''),
                        "parameters": trigger.get('parameters', [])
                    }
            
            # Map actions
            for action in data.get("actions", []):
                action_name = action.get('slug') or action.get('name')
                if action_name:
                    toolkit_mapping[slug]["actions"][action_name] = {
                        "name": action.get('name', action_name),
                        "description": action.get('description', ''),
                        "parameters": action.get('parameters', [])
                    }
        
        return toolkit_mapping

    def _generate_dynamic_example(self, catalog_context: Dict[str, Any]) -> str:
        """Generate a dynamic example based on the available tools in the catalog context."""
        
        # Find the first available toolkit with both triggers and actions
        example_toolkit = None
        example_trigger = None
        example_action = None
        
        for slug, data in catalog_context.get("toolkits", {}).items():
            if data.get("triggers") and data.get("actions"):
                example_toolkit = slug
                example_trigger = data["triggers"][0] if data["triggers"] else None
                example_action = data["actions"][0] if data["actions"] else None
                break
        
        if not example_toolkit or not example_trigger or not example_action:
            # Fallback to a generic example
            return self._get_fallback_example()
        
        # Extract the actual slugs/names
        trigger_slug = example_trigger.get('slug') or example_trigger.get('name') or "EXAMPLE_TRIGGER"
        action_name = example_action.get('slug') or example_action.get('name') or "EXAMPLE_ACTION"
        
        # Generate a contextual example
        example = f"""{{
"schema_type": "template",
"workflow": {{
"name": "Example Workflow using {example_toolkit.title()}",
"description": "Example workflow using {example_toolkit} toolkit",
"triggers": [{{
"id": "example_trigger",
"type": "event_based",
"toolkit_slug": "{example_toolkit}",
"composio_trigger_slug": "{trigger_slug}"
}}],
"actions": [{{
"id": "example_action",
"toolkit_slug": "{example_toolkit}",
"action_name": "{action_name}",
"required_inputs": [
{{ "name": "example_param", "source": "{{{{inputs.example_input}}}}", "type": "string" }}
],
"depends_on": ["example_trigger"]
}}]
}},
"missing_information": [{{
"field": "inputs.example_input",
"prompt": "What value should be used for the example parameter?",
"type": "string",
"required": true
}}]
}}"""
        
        return example
    
    def _get_fallback_example(self) -> str:
        """Return a fallback example when no suitable tools are available."""
        return """{
"schema_type": "template",
"workflow": {
"name": "Example Workflow",
"description": "Example workflow structure",
"triggers": [{
"id": "example_trigger",
"type": "event_based",
"toolkit_slug": "example_toolkit",
"composio_trigger_slug": "EXAMPLE_TRIGGER"
}],
"actions": [{
"id": "example_action",
"toolkit_slug": "example_toolkit",
"action_name": "EXAMPLE_ACTION",
"required_inputs": [
{ "name": "example_param", "source": "{{inputs.example_input}}", "type": "string" }
],
"depends_on": ["example_trigger"]
}]
},
"missing_information": [{
"field": "inputs.example_input",
"prompt": "What value should be used for the example parameter?",
"type": "string",
"required": true
}]
}}"""

    def _check_tool_hallucinations(self, dsl: Dict[str, Any], catalog_context: Dict[str, Any]) -> List[str]:
        """
        A simple, fast check to see if the LLM used tools that weren't in its context.
        Returns a list of error strings for feedback.
        """
        errors = []
        available_triggers = set()
        available_actions = set()

        # Build sets of available tools from catalog context
        for toolkit_slug, data in catalog_context.get("toolkits", {}).items():
            for t in data.get("triggers", []):
                available_triggers.add(f"{toolkit_slug}.{t.get('slug') or t.get('name')}")
            for a in data.get("actions", []):
                available_actions.add(f"{toolkit_slug}.{a.get('slug') or a.get('name')}")

        # Also check the triggers and actions lists directly (for the new format)
        for trigger in catalog_context.get("triggers", []):
            toolkit_slug = trigger.get("toolkit_slug", "")
            trigger_slug = trigger.get("trigger_slug", "") or trigger.get("slug", "")
            if toolkit_slug and trigger_slug:
                available_triggers.add(f"{toolkit_slug}.{trigger_slug}")

        for action in catalog_context.get("actions", []):
            toolkit_slug = action.get("toolkit_slug", "")
            action_slug = action.get("action_slug", "") or action.get("slug", "")
            if toolkit_slug and action_slug:
                available_actions.add(f"{toolkit_slug}.{action_slug}")

        workflow = dsl.get("workflow", {})
        
        # Check triggers
        for trigger in workflow.get("triggers", []):
            toolkit_slug = trigger.get("toolkit_slug", "")
            trigger_slug = trigger.get("composio_trigger_slug", "")
            if toolkit_slug and trigger_slug:
                slug = f"{toolkit_slug}.{trigger_slug}"
                if slug not in available_triggers:
                    errors.append(f"Invalid trigger: '{slug}'. It is not in the <available_tools> list.")
            
        # Check actions
        for action in workflow.get("actions", []):
            toolkit_slug = action.get("toolkit_slug", "")
            action_name = action.get("action_name", "")
            if toolkit_slug and action_name:
                slug = f"{toolkit_slug}.{action_name}"
                if slug not in available_actions:
                    errors.append(f"Invalid action: '{slug}'. It is not in the <available_tools> list.")
            
        return errors

    def _build_robust_claude_prompt(self, request: GenerationRequest, catalog_context: Dict[str, Any], previous_errors: List[str]) -> str:
        """Builds an aggressive, explicit prompt for Claude with clear tool context and strict validation rules."""
        
        # Create comprehensive toolkit mapping
        toolkit_mapping = self._create_toolkit_mapping(catalog_context)
        
        # --- IMPROVEMENT 1: Simplify the tool context ---
        tool_list_str = ""
        for slug, data in toolkit_mapping.items():
            tool_list_str += f"\n--- Toolkit: {slug} ---\n"
            if data.get("triggers"):
                tool_list_str += "Triggers:\n"
                for trigger_slug, trigger_data in data["triggers"].items():
                    tool_list_str += f"  - composio_trigger_slug: {trigger_slug}\n"
                    if trigger_data.get("description"):
                        tool_list_str += f"    Description: {trigger_data['description']}\n"
            if data.get("actions"):
                tool_list_str += "Actions:\n"
                for action_name, action_data in data["actions"].items():
                    tool_list_str += f"  - action_name: {action_name}\n"
                    if action_data.get("description"):
                        tool_list_str += f"    Description: {action_data['description']}\n"

        # Generate a dynamic example based on available tools
        dynamic_example = self._generate_dynamic_example(catalog_context)

        prompt = f"""<user_request>
{request.user_prompt}
</user_request>

<available_tools>
{tool_list_str}
</available_tools>

<instructions>
1. Design a logical, multi-step workflow.
2. Your output MUST conform to the `template` schema.
3. Every object in `required_inputs` MUST have a "name", "source", and "type" key.
4. Populate the `missing_information` array for any user inputs needed.
5. Your response MUST be a single, valid JSON object and nothing else.
6. NEVER invent or modify toolkit_slug, composio_trigger_slug, or action_name values.
7. ONLY use the exact values from the <available_tools> section above.
8. If you're unsure about a value, use the first available option from the list.
9. Every parameter MUST have a "type" field - this is CRITICAL for validation.
10. Use "string", "number", "boolean", or "array" as type values.
11. COPY AND PASTE the exact slug/name values - do not modify them.
12. Your JSON MUST be parseable by Python's json.loads().
</instructions>

<dynamic_example>
{dynamic_example}
</dynamic_example>

<validation_rules>
CRITICAL: Your JSON MUST pass these validation rules:
- All required_inputs objects MUST have: name, source, type
- All toolkit_slug values MUST exist in the available_tools
- All composio_trigger_slug values MUST exist in the available_tools  
- All action_name values MUST exist in the available_tools
- No markdown formatting or code blocks
- Pure JSON only
- Every field must be properly quoted
- No trailing commas
</validation_rules>

<error_prevention>
COMMON MISTAKES TO AVOID:
- Do NOT add markdown formatting like ```json
- Do NOT add explanatory text before or after the JSON
- Do NOT use placeholder values like "UNKNOWN_ACTION_NAME"
- Do NOT invent new toolkit slugs or action names
- Do NOT forget the "type" field in required_inputs
- Do NOT use unquoted strings in JSON
</error_prevention>
"""
        if previous_errors:
            errors_str = "\n".join(f"- {e}" for e in previous_errors)
            prompt += f"""
<feedback>
Your previous attempt failed. You MUST fix these errors:
{errors_str}

IMPORTANT: Read the error messages carefully and fix each one before generating your response.
</feedback>
"""
        # --- IMPROVEMENT 2: The Golden Rule at the end ---
        prompt += """

**CRITICAL FINAL INSTRUCTION:** 
1. You MUST only use the exact `composio_trigger_slug` and `action_name` values from the `<available_tools>` list.
2. Do not invent or modify them.
3. Copy the values exactly as they appear.
4. Generate ONLY the JSON response - no other text.
5. Ensure your JSON is valid and parseable.

Now, generate the complete JSON for the user's request."""
        
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

                # --- NEW: AGGRESSIVE PRE-VALIDATION CHECK ---
                if parsed_response.dsl_template:
                    # Convert DSL template to dict for checking
                    dsl_dict = parsed_response.dsl_template
                    if hasattr(dsl_dict, 'dict'):
                        dsl_dict = dsl_dict.dict()
                    elif hasattr(dsl_dict, 'workflow'):
                        dsl_dict = {'workflow': dsl_dict.workflow}
                        if hasattr(dsl_dict['workflow'], 'dict'):
                            dsl_dict['workflow'] = dsl_dict['workflow'].dict()
                    
                    tool_errors = self._check_tool_hallucinations(dsl_dict, catalog_context)
                    if tool_errors:
                        logger.warning(f"Tool Hallucination Detected: {tool_errors}")
                        previous_errors.extend(tool_errors)
                        continue  # Force a retry with this specific feedback
                # ---------------------------------------------

                # Perform custom validation against available tools
                if parsed_response.dsl_template and hasattr(parsed_response.dsl_template, 'workflow'):
                    workflow_data = parsed_response.dsl_template.workflow
                    if isinstance(workflow_data, dict):
                        # Convert to dict if it's a Pydantic model
                        if hasattr(workflow_data, 'dict'):
                            workflow_dict = workflow_data.dict()
                        else:
                            workflow_dict = workflow_data
                        
                        # Validate against available tools
                        validation_errors = self._validate_generated_workflow(workflow_dict, catalog_context)
                        
                        if validation_errors:
                            logger.warning(f"Custom validation failed with {len(validation_errors)} errors: {validation_errors}")
                            previous_errors.extend(validation_errors)
                            continue
                        else:
                            logger.info("Custom validation passed - workflow uses valid tools")
                    else:
                        logger.warning("Generated workflow is not in expected format")
                        previous_errors.append("Generated workflow format is invalid")
                        continue

                # --- THIS IS THE FIX ---
                # ALWAYS validate the generated DSL against the catalog context
                logger.info("Validating generated workflow against catalog context...")
                
                # Convert DSL template to dict for validation
                dsl_dict = parsed_response.dsl_template
                if hasattr(dsl_dict, 'dict'):
                    dsl_dict = dsl_dict.dict()
                elif hasattr(dsl_dict, 'workflow'):
                    dsl_dict = {'workflow': dsl_dict.workflow}
                    if hasattr(dsl_dict['workflow'], 'dict'):
                        dsl_dict['workflow'] = dsl_dict['workflow'].dict()
                
                # Check for tool hallucinations first (fast check)
                tool_errors = self._check_tool_hallucinations(dsl_dict, catalog_context)
                
                # Perform comprehensive validation using WorkflowValidator
                try:
                    # Create GenerationContext for the validator
                    schema_definition = self.context_builder._load_schema_definition()
                    catalog_context_obj = CatalogContext(
                        available_providers=list(catalog_context.get('providers', {}).values()),
                        available_triggers=catalog_context.get('triggers', []),
                        available_actions=catalog_context.get('actions', []),
                        provider_categories=[]
                    )
                    
                    generation_context = GenerationContext(
                        request=request,
                        catalog=catalog_context_obj,
                        schema_definition=schema_definition
                    )
                    
                    # Use WorkflowValidator for comprehensive validation
                    validation_result = await self.workflow_validator.validate_generated_workflow(
                        dsl_dict, 
                        generation_context, 
                        "template"  # Assuming template workflow type
                    )
                    
                    # Extract validation errors from the result
                    validation_errors = validation_result.get('validation_errors', [])
                    lint_errors = validation_result.get('lint_errors', [])
                    
                    # Combine all validation errors
                    all_errors = tool_errors + validation_errors + lint_errors
                    
                    if not all_errors:
                        logger.info("Generated workflow passed comprehensive validation successfully!")
                        return parsed_response
                    else:
                        logger.warning(f"Validation failed with {len(all_errors)} errors: {all_errors}")
                        previous_errors.extend(all_errors)
                        # The loop will continue to the next attempt with specific feedback
                        
                except Exception as validation_exception:
                    logger.error(f"Error during comprehensive validation: {validation_exception}")
                    # Fall back to basic validation if WorkflowValidator fails
                    basic_validation_errors = self._validate_generated_workflow(dsl_dict, catalog_context)
                    all_errors = tool_errors + basic_validation_errors
                    
                    if not all_errors:
                        logger.info("Generated workflow passed basic validation successfully!")
                        return parsed_response
                    else:
                        logger.warning(f"Basic validation failed with {len(all_errors)} errors: {all_errors}")
                        previous_errors.extend(all_errors)
                        # The loop will continue to the next attempt with specific feedback

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